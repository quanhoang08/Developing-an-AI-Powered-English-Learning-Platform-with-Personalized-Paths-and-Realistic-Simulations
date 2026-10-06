from fastapi.testclient import TestClient

from app.services import llm_service, toeic_service


async def _no_bank(*args, **kwargs) -> list:
	return []  # ngân hàng thật trong DB không được chen vào các test dùng LLM giả
from tests.test_vocab_integration import login, vocab_client  # noqa: F401  (fixture)


def _item(i: int) -> dict:
	return {
		"prompt": f"The report ___ by Friday {i}.", "passage": "", "correct_index": 1,
		"options": [f"submit{i}", "must be submitted", f"submitting{i}", f"submission{i}"], "explanation_vi": "Bị động sau must.",
	}


def test_clean_items_drops_malformed() -> None:
	good = _item(0)
	items = [
		good,
		{**good, "options": ["a", "a", "b", "c"]},  # trùng lựa chọn
		{**good, "prompt": "No blank here."},  # Part 5 thiếu chỗ trống
		{**good, "correct_index": 9},
		{**good, "options": ["one", "two", "three"]},  # sai số lựa chọn
		{**good, "prompt": "We meet in _____.", "options": ["in Tokyo", "Tokyo", "the city", "town"]},  # lặp "in"
	]
	cleaned = toeic_service.clean_items(5, items)
	assert len(cleaned) == 1 and cleaned[0]["prompt"].count("_____") == 1
	part2 = {**good, "prompt": "When is it due?", "options": ["Friday", "Yes", "In room 4"]}
	assert len(toeic_service.clean_items(2, [part2])) == 1
	q7 = {**good, "passage": "Email text", "prompt": "What is the purpose of the email?", "correct_index": 0}
	assert len(toeic_service.clean_items(7, [q7, {**q7, "prompt": "Email: Invitation"}])) == 1  # Part 7 phải là câu hỏi
	assert toeic_service.clean_items(7, [{**q7, "passage": ""}]) == []  # thiếu bài đọc
	assert toeic_service.clean_items(7, [{**q7, "prompt": "Mục đích của email là gì?"}]) == []  # đề phải là tiếng Anh
	q6 = {**good, "passage": "Dear Sam, we [1] a [2] meeting [3].", "prompt": "Blank [1]"}
	assert len(toeic_service.clean_items(6, [q6, {**q6, "passage": "No blanks here"}])) == 1


def test_shuffle_options_keeps_correct_answer() -> None:
	item = _item(0)
	seen = set()
	for _ in range(40):
		shuffled = toeic_service.shuffle_options(item)
		assert shuffled["options"][shuffled["correct_index"]] == "must be submitted"
		assert sorted(shuffled["options"]) == sorted(item["options"])
		seen.add(shuffled["correct_index"])
	assert len(seen) > 1  # không còn luôn nằm một chỗ


def test_estimate_scales_and_needs_both_sections() -> None:
	only_listening = toeic_service.estimate({2: (5, 5)})
	assert (only_listening["listening"], only_listening["reading"], only_listening["total"]) == (495, None, None)
	both = toeic_service.estimate({2: (0, 5), 5: (5, 10), 7: (0, 0)})
	assert (both["listening"], both["reading"], both["total"]) == (5, 250, 255)


def test_practice_flow_grades_on_server(vocab_client: TestClient, monkeypatch) -> None:
	monkeypatch.setattr(toeic_service, "_from_bank", _no_bank)
	async def fake_generate(part: int, count: int) -> list[dict]:
		return [_item(i) for i in range(count)]

	async def fake_solve(items: list[dict]) -> list[int]:
		return [[1]] * (len(items) - 2) + [[0], [1, 2]]  # câu áp chót làm khác đáp án, câu cuối có 2 đáp án -> cả hai bị loại

	monkeypatch.setattr(toeic_service, "shuffle_options", lambda item: item)  # test chấm điểm cần đáp án cố định
	monkeypatch.setattr(llm_service, "generate_toeic_items", fake_generate)
	monkeypatch.setattr(llm_service, "solve_toeic_items", fake_solve)
	headers = login(vocab_client)
	# mỗi vòng sinh 6 câu, bỏ 2 câu (làm khác / mơ hồ), còn 4 câu đã kiểm chứng = đúng số câu yêu cầu.
	start = vocab_client.post("/api/toeic/practice", headers=headers, json={"part": 5, "count": 4}).json()
	assert len(start["questions"]) == 4 and start["time_limit_seconds"] == 120
	assert "correct_index" not in start["questions"][0]

	picks = [1, 1, 0, None]  # đúng 2/4
	done = vocab_client.post(f"/api/toeic/{start['attempt_id']}/submit", headers=headers, json={"picks": picks}).json()
	assert (done["correct_count"], done["total"], done["score"]) == (2, 4, 50.0)
	assert [r["is_correct"] for r in done["results"]] == [True, True, False, False]
	again = vocab_client.post(f"/api/toeic/{start['attempt_id']}/submit", headers=headers, json={"picks": [0] * 4}).json()
	assert again["correct_count"] == 2  # idempotent

	errors = vocab_client.get("/api/adaptive/errors?error_type=grammar", headers=headers).json()
	assert [e["detail"]["source"] for e in errors] == ["toeic_part5", "toeic_part5"]
	summary = vocab_client.get("/api/toeic/summary", headers=headers).json()
	assert summary["parts"] == [{"part": 5, "attempts": 1, "questions": 4, "accuracy": 50.0}]
	assert summary["estimate"]["reading"] == 250 and summary["estimate"]["total"] is None

	assert vocab_client.post("/api/toeic/practice", headers=headers, json={"part": 8}).status_code == 422  # Part không tồn tại


def test_verification_helpers() -> None:
	a, b, c = (_item(i) for i in range(3))
	b["options"][0] = a["options"][0]  # b lặp lựa chọn sai của a
	assert toeic_service.drop_repeated_distractors([a, b, c]) == [a, c]
	assert toeic_service.only_verified([a, b, c], [[1], [1, 0], [2]]) == [a]  # b mơ hồ, c khác đáp án


def test_part6_unverified_blank_is_filled_and_renumbered() -> None:
	text = "We [1] the meeting on [2] because [3] is ill."
	mk = lambda n, opts, ok: {"prompt": f"Blank [{n}]", "passage": text, "options": opts, "correct_index": ok, "explanation_vi": ""}  # noqa: E731
	items = [mk(1, ["moved", "move", "moving", "moves"], 0), mk(2, ["Friday", "Fridays", "fri", "Frid"], 0), mk(3, ["she", "her", "hers", "herself"], 0)]
	out = toeic_service.keep_verified_blanks(items, [items[0], items[2]])  # chỗ trống [2] không kiểm chứng được
	assert [o["prompt"] for o in out] == ["Blank [1]", "Blank [2]"]
	assert out[0]["passage"] == "We [1] the meeting on Friday because [2] is ill."
	assert out[1]["options"][0] == "she"


def test_part6_answer_repeating_neighbour_word_is_dropped() -> None:
	good = _item(0)
	q = {**good, "passage": "We launch a new [1] service. Call [2] today and [3].", "prompt": "Blank [1]", "options": ["service", "product", "line", "plan"], "correct_index": 0}
	ok = {**q, "prompt": "Blank [2]", "options": ["us", "we", "our", "ours"]}
	ok3 = {**q, "prompt": "Blank [3]", "options": ["order", "orders", "ordered", "ordering"]}
	assert [i["prompt"] for i in toeic_service.clean_items(6, [q, ok, ok3])] == ["Blank [2]", "Blank [3]"]


def test_single_passage_picks_best_round_and_never_uses_unverified(vocab_client: TestClient, monkeypatch) -> None:
	monkeypatch.setattr(toeic_service, "_from_bank", _no_bank)
	rounds = []

	async def fake_generate(part: int, count: int) -> list[dict]:
		rounds.append(1)
		return [{**_item(i), "passage": "Dear team, please read [1] and [2] and [3] carefully.", "prompt": f"Blank [{i + 1}]",
			"options": [f"a{i}", f"b{i}", f"c{i}", f"d{i}"], "correct_index": 0} for i in range(3)]

	async def fake_solve(items: list[dict]) -> list[list[int]]:
		# solver không đồng ý câu nào ở vòng đầu; vòng sau đồng ý đúng 1 câu (theo đáp án đã xáo)
		return [[it["correct_index"]] if len(rounds) > 1 and n == 0 else [] for n, it in enumerate(items)]

	monkeypatch.setattr(llm_service, "generate_toeic_items", fake_generate)
	monkeypatch.setattr(llm_service, "solve_toeic_items", fake_solve)
	headers = login(vocab_client)
	start = vocab_client.post("/api/toeic/practice", headers=headers, json={"part": 6}).json()
	# chỉ 1 chỗ trống đã kiểm chứng, 2 chỗ trống kia được điền sẵn đáp án vào bài đọc, số chỗ trống đánh lại [1]
	assert len(start["questions"]) == 1 and start["questions"][0]["prompt"] == "Blank [1]"
	assert "[2]" not in start["questions"][0]["passage"] and "b1" not in start["questions"][0]["passage"]
	assert len(rounds) == 5  # chưa có vòng nào đủ 2 câu nên thử hết 5 vòng


def test_one_failed_llm_call_only_costs_one_attempt(vocab_client: TestClient, monkeypatch) -> None:
	monkeypatch.setattr(toeic_service, "_from_bank", _no_bank)
	calls = []

	async def flaky_generate(part: int, count: int) -> list[dict]:
		calls.append(1)
		if len(calls) == 1:
			raise llm_service.AIServiceError("ollama timeout", "ollama_timeout")
		return [_item(i) for i in range(count)]

	async def solve_all(items: list[dict]) -> list[list[int]]:
		return [[it["correct_index"]] for it in items]

	monkeypatch.setattr(llm_service, "generate_toeic_items", flaky_generate)
	monkeypatch.setattr(llm_service, "solve_toeic_items", solve_all)
	headers = login(vocab_client)
	ok = vocab_client.post("/api/toeic/practice", headers=headers, json={"part": 5, "count": 4})
	assert ok.status_code == 200 and len(ok.json()["questions"]) == 4 and len(calls) == 2

	calls.clear()
	monkeypatch.setattr(llm_service, "generate_toeic_items", lambda p, c: (_ for _ in ()).throw(llm_service.AIServiceError("x", "ollama_timeout")))
	failing = vocab_client.post("/api/toeic/practice", headers=headers, json={"part": 5, "count": 4})
	assert failing.status_code == 504  # nguyên nhân thật (Ollama timeout) được giữ lại


def test_letter_prefixes_stripped_and_part5_requires_short_options() -> None:
	good = _item(0)
	prefixed = {**good, "options": ["A) approve", "B) approval", "C) approving", "D) approved"], "correct_index": 3}
	cleaned = toeic_service.clean_items(5, [prefixed])
	assert cleaned[0]["options"] == ["approve", "approval", "approving", "approved"]
	assert "A new plan" == toeic_service._LETTER_PREFIX.sub("", "A new plan")  # chữ cái không kèm dấu thì giữ nguyên
	long_opts = {**good, "options": ["to ensure accuracy and transparency", "to ensure accuracy only", "neither one", "both"]}
	assert toeic_service.clean_items(5, [long_opts]) == []


def test_part5_drops_invented_word_distractors() -> None:
	good = _item(0)
	bogus = {**good, "prompt": "The company will _____ a new policy.", "options": ["introduces", "introduceing", "introduce", "introduceed"], "correct_index": 2}
	real = {**bogus, "options": ["introduces", "introducing", "introduce", "introduced"]}
	assert toeic_service.clean_items(5, [bogus, real]) == toeic_service.clean_items(5, [real]) and len(toeic_service.clean_items(5, [bogus, real])) == 1


def test_pick_units_prefers_unseen_and_avoids_repeated_distractors() -> None:
	def unit(i: int, wrong: list[str]) -> tuple:
		return (f"id{i}", {"questions": [{"prompt": f"q{i}", "options": ["right", *wrong], "correct_index": 0, "explanation_vi": ""}]})

	rows = [unit(1, ["a", "b", "c"]), unit(2, ["a", "x", "y"]), unit(3, ["m", "n", "o"]), unit(4, ["p", "q", "r"])]
	picked = toeic_service.pick_units(rows, {"id3"}, 5, 3)
	prompts = [q["prompt"] for q in picked]
	assert len(picked) == 3 and not {"q1", "q2"} <= set(prompts)  # q1 và q2 lặp đáp án nhiễu "a"
	assert all(q["bank_id"].startswith("id") and q["options"][q["correct_index"]] == "right" for q in picked)
	assert "q4" in prompts  # q3 đã gặp nên nhường chỗ cho câu chưa gặp
	assert toeic_service.pick_units(rows, set(), 5, 9) == []  # ngân hàng không đủ -> sinh trực tiếp
	passage_unit = ("p1", {"questions": [{"prompt": "Blank [1]", "passage": "text [1]", "options": ["a", "b", "c", "d"], "correct_index": 2, "explanation_vi": ""}]})
	assert toeic_service.pick_units([passage_unit], set(), 6, 3) == []  # chỉ 1 bài trong ngân hàng: sinh trực tiếp
	three = [passage_unit, ("p2", passage_unit[1]), ("p3", passage_unit[1])]
	assert len(toeic_service.pick_units(three, set(), 6, 3)) == 1  # đủ bài: phát 1 bài đọc


_DIALOGUE = "Man: Did you book the room?\nWoman: Not yet, I will do it now.\nMan: Please make it for ten people.\nWoman: Sure, the meeting is at noon."


def test_part3_requires_dialogue_and_part4_a_talk() -> None:
	q = {**_item(0), "passage": _DIALOGUE, "prompt": "What will the woman do next?", "correct_index": 0}
	assert len(toeic_service.clean_items(3, [q])) == 1
	assert toeic_service.clean_items(3, [{**q, "passage": "Just one long monologue without speaker labels at all."}]) == []  # không phải hội thoại
	assert toeic_service.clean_items(3, [{**q, "prompt": "Book the room"}]) == []  # phải là câu hỏi
	assert toeic_service.clean_items(3, [{**q, "passage": ""}]) == []  # thiếu bài nghe
	talk = {**q, "passage": "Good morning, everyone. The office will close early on Friday for maintenance."}
	assert len(toeic_service.clean_items(4, [talk])) == 1


def test_listening_estimate_combines_parts_2_3_4() -> None:
	est = toeic_service.estimate({2: (0, 5), 3: (5, 5), 5: (10, 10)})
	assert (est["listening"], est["reading"]) == (250, 495)  # 5/10 nghe đúng -> 250


def test_part3_practice_flow_awards_listening_activity(vocab_client: TestClient, monkeypatch) -> None:
	monkeypatch.setattr(toeic_service, "_from_bank", _no_bank)

	async def fake_generate(part: int, count: int) -> list[dict]:
		return [{**_item(i), "passage": _DIALOGUE, "prompt": f"Question {i}?", "options": [f"a{i}", f"b{i}", f"c{i}", f"d{i}"], "correct_index": 0} for i in range(3)]

	async def solve_all(items: list[dict]) -> list[list[int]]:
		return [[it["correct_index"]] for it in items]

	monkeypatch.setattr(toeic_service, "shuffle_options", lambda item: item)  # chấm điểm cần đáp án cố định
	monkeypatch.setattr(llm_service, "generate_toeic_items", fake_generate)
	monkeypatch.setattr(llm_service, "solve_toeic_items", solve_all)
	headers = login(vocab_client)
	start = vocab_client.post("/api/toeic/practice", headers=headers, json={"part": 3}).json()
	assert len(start["questions"]) == 3 and start["time_limit_seconds"] == 120 and start["questions"][0]["passage"] == _DIALOGUE
	done = vocab_client.post(f"/api/toeic/{start['attempt_id']}/submit", headers=headers, json={"picks": [0, 0, 0]}).json()
	assert (done["correct_count"], done["total"]) == (3, 3)
	assert vocab_client.get("/api/toeic/summary", headers=headers).json()["parts"][0]["part"] == 3


def test_part3_one_line_dialogue_is_split_into_turns() -> None:
	one_line = "Man: We need the schedule. Woman: Okay, let me check. Man: Is the room free? Woman: Yes, it is booked for noon."
	q = {**_item(0), "passage": one_line, "prompt": "What are they discussing?", "correct_index": 0}
	cleaned = toeic_service.clean_items(3, [q])
	assert len(cleaned) == 1 and cleaned[0]["passage"].count("\n") == 3 and cleaned[0]["passage"].startswith("Man: We need")


def test_part1_photo_items_are_well_formed_and_served(vocab_client: TestClient) -> None:
	items = toeic_service._part1_items()
	assert len(items) >= 12
	for file, item in items.items():
		assert (toeic_service._PART1_DIR / file).stat().st_size > 10_000  # ảnh thật có trong repo
		options = [item["correct"], *item["wrong"]]
		assert len(options) == 4 and len({o.lower() for o in options}) == 4 and item["explanation_vi"] and "Wikimedia" in item["credit"]
	headers = login(vocab_client)
	start = vocab_client.post("/api/toeic/practice", headers=headers, json={"part": 1, "count": 4}).json()
	assert len(start["questions"]) == 4 and start["time_limit_seconds"] == 80
	assert len({q["image"] for q in start["questions"]}) == 4  # mỗi câu một ảnh khác nhau
	image = vocab_client.get(f"/api/toeic/part1/images/{start['questions'][0]['image']}", headers=headers)
	assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg" and image.content[:2] == b"\xff\xd8"
	assert vocab_client.get("/api/toeic/part1/images/..%2F..%2Fmain.py", headers=headers).status_code == 404
	assert vocab_client.get("/api/toeic/part1/images/01.jpg").status_code in (401, 403)  # cần đăng nhập
	done = vocab_client.post(f"/api/toeic/{start['attempt_id']}/submit", headers=headers, json={"picks": [None] * 4}).json()
	assert done["correct_count"] == 0 and all(r["explanation_vi"] and r["contrast_vi"] for r in done["results"])


def test_mock_exam_combines_parts_and_reports_breakdown(vocab_client: TestClient, monkeypatch) -> None:
	headers = login(vocab_client)
	start = vocab_client.post("/api/toeic/mock", headers=headers).json()
	questions = start["questions"]
	parts = [q["part"] for q in questions]
	assert parts[:6] == [1] * 6 and parts == sorted(parts) and {2, 5} <= set(parts)  # Part 1 trước, theo thứ tự Part
	assert start["time_limit_seconds"] == 36 * len(questions)
	groups = {}
	for q in questions:
		if q["group"] is not None:
			groups.setdefault(q["group"], []).append(q)
	assert all(len({x["passage"] for x in g}) == 1 and len({x["part"] for x in g}) == 1 for g in groups.values())  # câu cùng bài cùng Part

	done = vocab_client.post(f"/api/toeic/{start['attempt_id']}/submit", headers=headers, json={"picks": [None] * len(questions)}).json()
	assert done["total"] == len(questions) and done["correct_count"] == 0
	assert [b["part"] for b in done["by_part"]] == sorted(set(parts)) and sum(b["total"] for b in done["by_part"]) == len(questions)
	assert done["estimate"]["listening"] == 5 and done["estimate"]["reading"] == 5  # 0 đúng -> điểm sàn
	assert all(r["contrast_vi"] for r in done["results"])

	monkeypatch.setattr(toeic_service, "_MOCK_MIN_QUESTIONS", 10_000)
	assert vocab_client.post("/api/toeic/mock", headers=headers).status_code == 409  # ngân hàng quá ít
