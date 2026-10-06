# Luyện TOEIC-style (backlog 2.7). Đề là câu hỏi GỐC do LLM sinh theo định dạng TOEIC (không lấy đề ETS), nên
# luôn gắn nhãn "TOEIC-style"; sinh dư rồi cho model tự làm lại, câu nào model làm khác đáp án sinh thì bỏ.
import json
import random
import re
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import wordfreq
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.toeic import ToeicAttempt, ToeicBankUnit
from app.services import adaptive_service, llm_service
from app.services.gamification_service import award_activity

PARTS = (1, 2, 3, 4, 5, 6, 7)
LISTENING_PARTS = (1, 2, 3, 4)
SINGLE_PASSAGE = (3, 4, 6, 7)  # 1 bài (hội thoại/bài nói/bài đọc) + 3 câu; Part 3/4 phát bằng TTS, bài ẩn tới khi nộp
OPTION_COUNT = {1: 4, 2: 3, 3: 4, 4: 4, 5: 4, 6: 4, 7: 4}
SECONDS_PER_QUESTION = {1: 20, 2: 20, 3: 40, 4: 40, 5: 30, 6: 60, 7: 75}
_ERROR_TYPE = {1: "listening_comprehension", 2: "listening_comprehension", 3: "listening_comprehension", 4: "listening_comprehension", 5: "grammar", 6: "grammar", 7: "reading_comprehension"}
_PART1_DIR = Path(__file__).resolve().parent.parent / "data" / "toeic_part1"
_PART1_PROMPT = "Look at the picture and choose the statement that best describes it."
_TURN_BREAK = re.compile(r"(?<=[.?!'\"])[ \t]+(?=[A-Z][A-Za-z.]*(?: [A-Z][a-z]+)?:\s)")  # khoảng trắng ngay trước nhãn người nói
_SPEAKER_LINE = re.compile(r"^\s*[A-Z][A-Za-z .]{0,20}:\s+\S", re.MULTILINE)  # "Man: ...", "Ms. Lee: ..."
_MIN_QUESTIONS = 3
_BUDGET_SECONDS = 150
_MIN_PASSAGES_IN_BANK = 3
_ROUND_SIZE = 6  # sinh ít câu mỗi lần: nhanh hơn và model ít treo hơn so với 1 lần 12+ câu
# Model hay viết sẵn "A) ..." trong lựa chọn; sau khi xáo chữ cái đó sẽ sai nên bỏ đi (giao diện tự gắn A-D).
_LETTER_PREFIX = re.compile(r"^\(?[A-Da-d][\).:]\s+")
_PART5_MAX_WORDS = 4
_MIN_ZIPF = 1.0  # từ có thật; dạng bịa như "introduceing" có tần suất 0
_MIN_QUESTIONS_PART_2_5 = 2  # đề ít câu còn hơn báo lỗi (đồng hồ tính theo số câu)
# Chữ cái chỉ có trong tiếng Việt: đề (prompt/passage/options) phải là tiếng Anh, chỉ explanation_vi là tiếng Việt.
_VIETNAMESE = re.compile("[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.IGNORECASE)


def _repeats_word_before_blank(prompt: str, options: list[str]) -> bool:
	""""in _____" với lựa chọn "in Tokyo": từ đứng trước chỗ trống lặp ở đầu lựa chọn -> câu lỗi, bỏ."""
	before = prompt.split("_____")[0].split()
	return bool(before) and any(o.lower().split()[0] == before[-1].lower().strip(".,") for o in options if o.split())


def _has_invented_word(options: list[str]) -> bool:
	"""Model hay bịa dạng từ không tồn tại làm đáp án nhiễu ("introduceing", "submiting") -> câu không dùng được."""
	words = [w for o in options for w in re.findall(r"[A-Za-z]+", o)]
	return any(wordfreq.zipf_frequency(w.lower(), "en") < _MIN_ZIPF for w in words)


def _answer_repeats_neighbour(passage: str, prompt: str, answer: str) -> bool:
	"""Part 6: đáp án trùng từ đứng ngay trước/sau chỗ trống trong bài đọc (vd. "a new [1] service" -> "service")."""
	number = re.search(r"\d+", prompt)
	around = re.search(r"(\w+)\W*\[" + (number.group() if number else "0") + r"\]\W*(\w+)?", passage)
	return bool(around) and answer.lower() in {w.lower() for w in around.groups() if w}


def clean_items(part: int, items: list[dict]) -> list[dict]:
	"""Giữ câu đúng cấu trúc: đủ số lựa chọn khác nhau, correct_index hợp lệ, Part 5 có đúng 1 chỗ trống."""
	size = OPTION_COUNT[part]
	if part == 3:  # model hay viết cả hội thoại trên 1 dòng: tách mỗi lượt lời ("Man: ...") thành 1 dòng
		items = [{**i, "passage": _TURN_BREAK.sub("\n", i.get("passage") or "")} for i in items]
	good = []
	for item in items:
		options = [_LETTER_PREFIX.sub("", str(o).strip()) for o in item.get("options", [])]
		prompt = re.sub(r"_{2,}", "_____", str(item.get("prompt", "")).strip())
		index = item.get("correct_index")
		if (
			not prompt
			or len(options) != size
			or len({o.lower() for o in options}) != size
			or not all(options)
			or not isinstance(index, int)
			or not 0 <= index < size
			or (part == 5 and (prompt.count("_____") != 1 or _repeats_word_before_blank(prompt, options)))
			or _VIETNAMESE.search(" ".join([prompt, item.get("passage") or "", *options]))
			or (part in (3, 4, 7) and not prompt.endswith("?"))
			or (part == 3 and len(_SPEAKER_LINE.findall(item.get("passage") or "")) < 4)  # hội thoại cần >= 4 lượt lời "Man: ..."
			or (part == 5 and (max(len(o.split()) for o in options) > _PART5_MAX_WORDS or _has_invented_word(options)))  # Part 5 thật chỉ có lựa chọn ngắn
			or (part == 6 and _answer_repeats_neighbour(item.get("passage") or "", prompt, options[index]))
			or (part in SINGLE_PASSAGE and not (item.get("passage") or "").strip())  # Part 3/4/6/7 vô nghĩa nếu thiếu bài
			or (part == 6 and (any(f"[{k}]" not in item["passage"] for k in (1, 2, 3)) or max(len(o.split()) for o in options) > 6))
		):
			continue
		good.append(
			{
				"prompt": prompt,
				"passage": (item.get("passage") or "").strip() or None,
				"options": options,
				"correct_index": index,
				"explanation_vi": str(item.get("explanation_vi", "")).strip(),
			}
		)
	# Part 6: 3 chỗ trống dùng y hệt một bộ lựa chọn là đề hỏng (model hay lặp), bỏ cả bộ.
	if part == 6 and len(good) > 1 and len({tuple(sorted(g["options"])) for g in good}) == 1:
		return []
	return good


def shuffle_options(item: dict) -> dict:
	"""Model hay đặt đáp án đúng ở vị trí A (đo trên web: 10/10 câu) -> xáo lựa chọn và cập nhật correct_index."""
	correct = item["options"][item["correct_index"]]
	options = random.sample(item["options"], len(item["options"]))
	return {**item, "options": options, "correct_index": options.index(correct)}


def drop_repeated_distractors(items: list[dict]) -> list[dict]:
	"""Cùng một lựa chọn sai xuất hiện ở nhiều câu (model hay lặp) -> chỉ giữ câu đầu tiên dùng nó."""
	seen: set[str] = set()
	kept = []
	for item in items:
		wrong = {o.lower() for i, o in enumerate(item["options"]) if i != item["correct_index"]}
		if wrong & seen:
			continue
		seen |= wrong
		kept.append(item)
	return kept


def only_verified(items: list[dict], acceptable: list[list[int]]) -> list[dict]:
	"""Giữ câu mà model tự làm lại chỉ thấy đúng 1 lựa chọn chấp nhận được và trùng đáp án sinh."""
	return [it for it, ok in zip(items, acceptable) if set(ok) == {it["correct_index"]}]


def keep_verified_blanks(items: list[dict], verified: list[dict]) -> list[dict]:
	"""Part 6: chỗ trống không kiểm chứng được thì điền sẵn đáp án vào bài đọc, các chỗ trống còn lại đánh số lại [1], [2]..."""
	number = lambda item: int(re.search(r"\d+", item["prompt"]).group())  # noqa: E731
	kept = {number(v): v for v in verified}
	passage = items[0]["passage"]
	for item in items:
		if number(item) not in kept:
			passage = passage.replace(f"[{number(item)}]", item["options"][item["correct_index"]])
	order = sorted(kept)
	for new, old in enumerate(order, 1):
		passage = passage.replace(f"[{old}]", f"<<{new}>>")
	passage = re.sub(r"<<(\d+)>>", r"[\1]", passage)
	return [{**kept[old], "passage": passage, "prompt": f"Blank [{new}]"} for new, old in enumerate(order, 1)]


def pick_units(rows: list[tuple], seen_ids: set[str], part: int, want: int) -> list[dict]:
	"""Chọn đề từ ngân hàng. rows = [(id, unit)]. Part 2/5: `want` câu (mỗi unit 1 câu); Part 6/7: 1 bài đọc.
	Ưu tiên đơn vị người học chưa gặp ở 10 lượt gần nhất, hết thì lấy cả đã gặp; ngân hàng không đủ -> [] (sinh trực tiếp)."""
	fresh = [r for r in rows if str(r[0]) not in seen_ids]
	old = [r for r in rows if str(r[0]) in seen_ids]
	random.shuffle(fresh)
	random.shuffle(old)
	need = 1 if part in SINGLE_PASSAGE else want
	if part in SINGLE_PASSAGE and len(rows) < _MIN_PASSAGES_IN_BANK:
		return []  # ngân hàng quá ít bài đọc thì ai cũng gặp lại cùng một bài: sinh trực tiếp
	chosen: list[tuple] = []
	used_wrong: set[str] = set()
	for row in fresh + old:
		if len(chosen) >= need:
			break
		q = row[1]["questions"][0]
		wrong = {o.lower() for i, o in enumerate(q["options"]) if i != q["correct_index"]}
		if part in (2, 5) and wrong & used_wrong:
			continue  # cùng một đáp án nhiễu không xuất hiện ở 2 câu trong một lượt
		used_wrong |= wrong
		chosen.append(row)
	if len(chosen) < need:
		return []
	# Xáo lại lựa chọn mỗi lần phát để cùng một câu không luôn có đáp án ở một chỗ.
	return [shuffle_options({**q, "bank_id": str(uid)}) for uid, unit in chosen for q in unit["questions"]]


async def _from_bank(db: AsyncSession, user_id: uuid.UUID, part: int, want: int) -> list[dict]:
	rows = (
		await db.execute(select(ToeicBankUnit.id, ToeicBankUnit.unit).where(ToeicBankUnit.part == part, ToeicBankUnit.disabled.is_(False)))
	).all()
	if not rows:
		return []
	recent = await db.scalars(
		select(ToeicAttempt.questions).where(ToeicAttempt.user_id == user_id, ToeicAttempt.part == part).order_by(ToeicAttempt.created_at.desc()).limit(10)
	)
	seen = {q.get("bank_id") for questions in recent for q in questions}
	return pick_units([tuple(r) for r in rows], seen, part, want)


@lru_cache(maxsize=1)
def _part1_items() -> dict[str, dict]:
	"""Part 1 (mô tả ảnh): ảnh Wikimedia Commons (CC0 / public domain / CC BY) + câu mô tả do tác giả đề tài viết tay
	sau khi xem ảnh. attribution.json giữ tác giả/giấy phép từng ảnh (hiển thị cho người học)."""
	items = json.loads((_PART1_DIR / "items.json").read_text(encoding="utf-8"))
	credits = {a["file"]: a for a in json.loads((_PART1_DIR / "attribution.json").read_text(encoding="utf-8"))}
	return {
		i["file"]: {**i, "credit": f"Photo: {credits[i['file']]['author']}, {credits[i['file']]['license']}, via Wikimedia Commons"}
		for i in items
	}


def part1_image_path(name: str) -> Path | None:
	"""Chỉ phục vụ file nằm trong danh sách ảnh đã khai báo (không đọc đường dẫn tuỳ ý từ client)."""
	return _PART1_DIR / name if name in _part1_items() else None


async def _create_part1(db: AsyncSession, user_id: uuid.UUID, count: int) -> ToeicAttempt:
	attempt = ToeicAttempt(user_id=user_id, part=1, questions=await _part1_questions(db, user_id, count))
	db.add(attempt)
	await db.commit()
	await db.refresh(attempt)
	return attempt


async def _part1_questions(db: AsyncSession, user_id: uuid.UUID, count: int) -> list[dict]:
	"""Không dùng LLM: ảnh chưa gặp ở 10 lượt gần nhất được ưu tiên; lựa chọn xáo lại mỗi lần phát."""
	recent = await db.scalars(
		select(ToeicAttempt.questions).where(ToeicAttempt.user_id == user_id, ToeicAttempt.part == 1).order_by(ToeicAttempt.created_at.desc()).limit(10)
	)
	seen = {q.get("image") for questions in recent for q in questions}
	pool = list(_part1_items().values())
	random.shuffle(pool)
	pool.sort(key=lambda i: i["file"] in seen)  # sort ổn định: ảnh chưa gặp lên trước
	questions = []
	for item in pool[: min(count, 6)]:
		options = [item["correct"], *item["wrong"]]
		questions.append(
			shuffle_options(
				{"prompt": _PART1_PROMPT, "passage": None, "image": item["file"], "credit": item["credit"], "options": options, "correct_index": 0, "explanation_vi": item["explanation_vi"]}
			)
		)
	return questions


# Đề thi thử: ghép Part 1-7 từ ngân hàng đã kiểm chứng (không sinh trực tiếp: quá chậm), 1 đồng hồ chung.
# Số lượng gần đề thật (200 câu); ngân hàng ít thì ít câu hơn, tối thiểu _MOCK_MIN_QUESTIONS.
MOCK_TARGETS = {2: 26, 3: 13, 4: 10, 5: 30, 6: 5, 7: 18}  # câu (Part 2/5) hoặc bài 3 câu (Part 3/4/6/7); + Part 1 6 ảnh = 200 câu
MOCK_SECONDS_PER_QUESTION = 36  # 2 giờ / 200 câu
_MOCK_MIN_QUESTIONS = 12


def _mock_units(rows: list[tuple], part: int, n: int, first_group: int) -> list[dict]:
	"""Chọn tối đa n đơn vị ngẫu nhiên từ ngân hàng của 1 Part; Part 3/4/6/7 gắn `group` để giao diện nhóm câu theo bài."""
	rows = random.sample(rows, len(rows))
	questions: list[dict] = []
	used_wrong: set[str] = set()
	taken = 0
	for uid, unit in rows:
		if taken >= n:
			break
		if part in (2, 5):
			q = unit["questions"][0]
			wrong = {o.lower() for i, o in enumerate(q["options"]) if i != q["correct_index"]}
			if wrong & used_wrong:
				continue  # cùng một đáp án nhiễu không xuất hiện ở 2 câu
			used_wrong |= wrong
		group = first_group + taken if part in SINGLE_PASSAGE else None
		questions += [{**shuffle_options({**q, "bank_id": str(uid)}), "part": part, "group": group} for q in unit["questions"]]
		taken += 1
	return questions


async def create_mock(db: AsyncSession, user_id: uuid.UUID) -> ToeicAttempt:
	questions = [{**q, "part": 1, "group": None} for q in await _part1_questions(db, user_id, 6)]
	group = 0
	for part, target in MOCK_TARGETS.items():
		rows = (await db.execute(select(ToeicBankUnit.id, ToeicBankUnit.unit).where(ToeicBankUnit.part == part, ToeicBankUnit.disabled.is_(False)))).all()
		picked = _mock_units([tuple(r) for r in rows], part, target, group)
		questions += picked
		group += len({q["group"] for q in picked if q["group"] is not None})
	if len(questions) < _MOCK_MIN_QUESTIONS:
		raise ValueError("bank_too_small")
	attempt = ToeicAttempt(user_id=user_id, part=0, questions=questions)  # part 0 = đề thi thử nhiều Part
	db.add(attempt)
	await db.commit()
	await db.refresh(attempt)
	return attempt


def part_breakdown(attempt: ToeicAttempt) -> dict[int, tuple[int, int]]:
	"""{part: (đúng, tổng)} của 1 lượt đã nộp (dùng cho đề thi thử)."""
	stats: dict[int, list[int]] = {}
	for item, pick in zip(attempt.questions, attempt.picks or []):
		part = item.get("part", attempt.part)
		counts = stats.setdefault(part, [0, 0])
		counts[0] += pick == item["correct_index"]
		counts[1] += 1
	return {p: (c, t) for p, (c, t) in sorted(stats.items())}


async def create_practice(db: AsyncSession, user_id: uuid.UUID, part: int, count: int) -> ToeicAttempt:
	"""Sinh đề rồi cho model tự làm lại để loại câu mơ hồ / sai đáp án.

	Part 2/5: gộp các câu đã kiểm chứng của tối đa 4 lần sinh (mỗi lần 6 câu) cho đến khi đủ hoặc hết ngân sách thời gian. Part 6/7 (1 bài đọc): chọn lần sinh có nhiều câu đã
	kiểm chứng nhất, dừng sớm khi có >= 2; chỉ còn 1 câu vẫn dùng được còn hơn báo lỗi (không bao giờ dùng câu chưa kiểm chứng).
	"""
	if part == 1:
		return await _create_part1(db, user_id, count)
	single_passage = part in SINGLE_PASSAGE
	want = 3 if single_passage else count
	# Ngân hàng đề đã kiểm chứng sẵn (script build_toeic_bank): phát ngay, đủ số câu. Thiếu mới sinh trực tiếp bên dưới.
	banked = await _from_bank(db, user_id, part, want)
	if banked:
		attempt = ToeicAttempt(user_id=user_id, part=part, questions=banked)
		db.add(attempt)
		await db.commit()
		await db.refresh(attempt)
		return attempt
	items: list[dict] = []
	best: list[dict] = []
	last_error: Exception | None = None
	deadline = time.monotonic() + _BUDGET_SECONDS  # quá hạn thì dừng thử thêm, dùng kết quả tốt nhất đang có
	for _ in range(5 if single_passage else 4):
		if time.monotonic() > deadline:
			break
		try:
			raw = clean_items(part, await llm_service.generate_toeic_items(part, 3 if single_passage else _ROUND_SIZE))
		except llm_service.AIServiceError as error:
			last_error = error  # 1 lời gọi hỏng/treo chỉ làm hỏng lần thử này, không phải cả yêu cầu
			continue
		if part == 6 and len(raw) != 3:
			continue  # thiếu chỗ trống nào là không biết đáp án chỗ đó để điền lại
		if not single_passage:
			raw = drop_repeated_distractors(raw)
		if not raw:
			continue
		# Xáo TRƯỚC khi cho model làm lại: đáp án sinh ra gần như luôn ở vị trí 0 nên solver sẽ "đồng ý" chỉ vì thiên vị vị trí.
		raw = [shuffle_options(it) for it in raw]
		try:
			checked = only_verified(raw, await llm_service.solve_toeic_items(raw))
		except llm_service.AIServiceError as error:
			last_error = error
			continue
		if single_passage:
			if part == 6 and checked:
				checked = keep_verified_blanks(raw, checked)
			if len(checked) > len(best):
				best = checked
			if len(best) >= 2:
				break
			continue
		seen = {it["prompt"] for it in items}
		# Lặp lại đáp án nhiễu giữa các vòng sinh cũng bị loại (vòng sau nhường vòng trước).
		items = drop_repeated_distractors(items + [it for it in checked if it["prompt"] not in seen])
		if len(items) >= want:
			break
	items = (best if single_passage else items)[:want]
	if len(items) < (1 if single_passage else _MIN_QUESTIONS_PART_2_5):
		# Nếu mọi lần thử đều lỗi LLM thì báo đúng nguyên nhân đó (vd. ollama_timeout) thay vì "đề hỏng".
		raise last_error or llm_service.AIServiceError("toeic_generation_failed", "ai_bad_output")
	attempt = ToeicAttempt(user_id=user_id, part=part, questions=items)
	db.add(attempt)
	await db.commit()
	await db.refresh(attempt)
	return attempt


def time_limit(attempt: ToeicAttempt) -> int:
	per_question = MOCK_SECONDS_PER_QUESTION if attempt.part == 0 else SECONDS_PER_QUESTION[attempt.part]
	return per_question * len(attempt.questions)


async def submit(
	db: AsyncSession, user_id: uuid.UUID, attempt_id: uuid.UUID, picks: list[int | None], duration_seconds: int | None
) -> ToeicAttempt:
	"""Chấm ở server, ghi user_errors cho câu sai, cộng XP. Idempotent: nộp lại trả kết quả cũ."""
	attempt = await db.scalar(
		select(ToeicAttempt).where(ToeicAttempt.id == attempt_id, ToeicAttempt.user_id == user_id)
	)
	if attempt is None:
		raise ValueError("attempt_not_found")
	if attempt.submitted_at is not None:
		return attempt
	if len(picks) != len(attempt.questions):
		raise ValueError("picks_length_mismatch")
	correct = 0
	sections: dict[str, list[int]] = {}  # hoạt động (nghe/đọc) -> [đúng, tổng]; đề thi thử có cả hai
	for item, pick in zip(attempt.questions, picks):
		part = item.get("part", attempt.part)
		kind = "toeic_listening_completed" if part in LISTENING_PARTS else "toeic_reading_completed"
		counts = sections.setdefault(kind, [0, 0])
		counts[1] += 1
		if pick == item["correct_index"]:
			correct += 1
			counts[0] += 1
			continue
		chosen = item["options"][pick] if isinstance(pick, int) and 0 <= pick < len(item["options"]) else None
		adaptive_service.record_error(
			db,
			user_id,
			_ERROR_TYPE[part],
			{
				"source": f"toeic_part{part}",
				"question": item["prompt"],
				"original_text": chosen or "(no answer)",
				"corrected_text": item["options"][item["correct_index"]],
				"explanation": item["explanation_vi"],
			},
		)
	score = round(correct / len(attempt.questions) * 100, 2)
	attempt.picks, attempt.correct_count, attempt.score = picks, correct, score
	attempt.submitted_at = datetime.now(timezone.utc)
	for index, (kind, (right, total)) in enumerate(sections.items()):
		await award_activity(
			db, user_id, kind, score=round(right / total * 100, 2),
			duration_seconds=duration_seconds if index == 0 else None,  # thời gian tính 1 lần, không nhân đôi
		)
	await db.commit()
	await db.refresh(attempt)
	return attempt


def _scaled(correct: int, total: int) -> int:
	"""Quy đổi tuyến tính accuracy -> 5..495 (làm tròn bội 5). Đề thật không tuyến tính; chỉ là ước lượng thô."""
	return 5 * round((5 + 490 * correct / total) / 5)


def estimate(stats: dict[int, tuple[int, int]]) -> dict:
	"""stats[part] = (số câu đúng, tổng câu) của các lượt gần nhất. Listening = Part 2/3/4; Reading = Part 5/6/7."""
	listening_parts = [stats[p] for p in LISTENING_PARTS if stats.get(p) and stats[p][1]]
	listening = _scaled(sum(c for c, _ in listening_parts), sum(t for _, t in listening_parts)) if listening_parts else None
	reading_parts = [stats[p] for p in (5, 6, 7) if stats.get(p) and stats[p][1]]
	reading = _scaled(sum(c for c, _ in reading_parts), sum(t for _, t in reading_parts)) if reading_parts else None
	return {
		"listening": listening,
		"reading": reading,
		"total": listening + reading if listening is not None and reading is not None else None,
		"note": "Rough estimate from a few AI-written practice questions, not an official TOEIC score.",
	}


async def summary(db: AsyncSession, user_id: uuid.UUID) -> dict:
	rows = (
		await db.scalars(
			select(ToeicAttempt)
			.where(ToeicAttempt.user_id == user_id, ToeicAttempt.submitted_at.is_not(None))
			.order_by(ToeicAttempt.submitted_at.desc())
			.limit(60)
		)
	).all()
	parts, recent = [], {}
	for part in PARTS:
		mine = [a for a in rows if a.part == part]
		total = sum(len(a.questions) for a in mine)
		correct = sum(a.correct_count for a in mine)
		if mine:
			parts.append({"part": part, "attempts": len(mine), "questions": total, "accuracy": round(100 * correct / total, 1)})
		last = mine[:5]  # ước lượng chỉ dựa 5 lượt gần nhất mỗi Part để phản ánh trình độ hiện tại
		recent[part] = (sum(a.correct_count for a in last), sum(len(a.questions) for a in last))
	return {"parts": parts, "estimate": estimate(recent)}
