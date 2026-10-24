from datetime import date

from fastapi.testclient import TestClient

from app.services import games_service
from tests.test_vocab_integration import login, vocab_client  # noqa: F401  (fixture)


def test_evaluate_handles_repeated_letters() -> None:
	assert games_service.evaluate("crane", "crane") == ["correct"] * 5
	# "eerie" vs "tepee": chữ e chỉ tô theo số lần còn lại trong đáp án.
	assert games_service.evaluate("eerie", "tepee") == ["present", "correct", "absent", "absent", "correct"]


def test_daily_word_is_stable_five_letters() -> None:
	word = games_service.daily_word(date(2026, 10, 23))
	assert word == games_service.daily_word(date(2026, 10, 23)) and len(word) == 5 and games_service.is_valid_guess(word)


def test_wordle_quest_and_memory_flow(vocab_client: TestClient) -> None:
	headers = login(vocab_client)
	assert vocab_client.get("/api/games/wordle", headers=headers).json()["solved_today"] is False

	bad = vocab_client.post("/api/games/wordle/guess", headers=headers, json={"guess": "zzzzz", "attempt": 1})
	assert bad.status_code == 422

	answer = games_service.daily_word(games_service.study_today())
	wrong = next(w for w in ("about", "house", "water") if w != answer)
	miss = vocab_client.post("/api/games/wordle/guess", headers=headers, json={"guess": wrong, "attempt": 1}).json()
	assert miss["solved"] is False and miss["answer"] is None and miss["xp_awarded"] == 0

	hit = vocab_client.post("/api/games/wordle/guess", headers=headers, json={"guess": answer, "attempt": 2}).json()
	assert hit["solved"] and hit["answer"] == answer and hit["xp_awarded"] == 10
	again = vocab_client.post("/api/games/wordle/guess", headers=headers, json={"guess": answer, "attempt": 3}).json()
	assert again["xp_awarded"] == 0
	assert vocab_client.get("/api/games/wordle", headers=headers).json()["solved_today"] is True

	# Nhiệm vụ "play_game" đã đủ nhờ Wordle: nhận 1 lần, lần 2 bị 409; nhiệm vụ chưa đủ cũng 409.
	quests = {q["id"]: q for q in vocab_client.get("/api/games/quests", headers=headers).json()}
	assert quests["play_game"]["progress"] == 1 and not quests["play_game"]["claimed"]
	assert vocab_client.post("/api/games/quests/play_game/claim", headers=headers).json() == {"xp_awarded": 10}
	assert vocab_client.post("/api/games/quests/play_game/claim", headers=headers).status_code == 409
	assert vocab_client.post("/api/games/quests/review_words/claim", headers=headers).status_code == 409
	assert vocab_client.post("/api/games/quests/nope/claim", headers=headers).status_code == 404

	# Memory match: ván hợp lệ có XP, cap 3 ván/ngày, ván bất thường bị từ chối.
	post = lambda: vocab_client.post("/api/games/memory-match/complete", headers=headers, json={"pairs": 6, "moves": 9})  # noqa: E731
	assert [post().json()["xp_awarded"] for _ in range(4)] == [8, 8, 8, 0]
	assert vocab_client.post("/api/games/memory-match/complete", headers=headers, json={"pairs": 6, "moves": 3}).status_code == 422
	assert vocab_client.get("/api/streaks", headers=headers).json()["total_xp"] == 10 + 10 + 24


def test_word_chain_rules() -> None:
	import pytest

	first = games_service.word_chain_turn([], "apple")
	assert first["reply"] and first["reply"][0] == "e"
	with pytest.raises(ValueError, match="wrong_start_letter"):
		games_service.word_chain_turn(["apple", "eagle"], "tiger" if False else "dog")
	with pytest.raises(ValueError, match="already_used"):
		games_service.word_chain_turn(["apple", "eagle"], "eagle")
	with pytest.raises(ValueError, match="not_in_word_list"):
		games_service.word_chain_turn([], "qqqzz")


def test_grammar_detective_and_score_games(vocab_client: TestClient) -> None:
	headers = login(vocab_client)
	passage = vocab_client.get("/api/games/grammar-detective", headers=headers).json()
	tokens, answers = games_service._parse_passage(passage["passage_id"])
	assert passage["tokens"] == tokens and passage["error_count"] == len(answers) and "answers" not in passage

	bad = vocab_client.post("/api/games/grammar-detective/check", headers=headers, json={"passage_id": passage["passage_id"], "picks": [0, 1, 2]})
	body = bad.json()
	assert body["answers"] and body["xp_awarded"] == 0 if body["found"] < body["total"] else True
	good = vocab_client.post("/api/games/grammar-detective/check", headers=headers, json={"passage_id": passage["passage_id"], "picks": list(answers)}).json()
	assert good["found"] == good["total"] and good["false_positives"] == 0 and good["xp_awarded"] == 10
	assert vocab_client.post("/api/games/grammar-detective/check", headers=headers, json={"passage_id": 99, "picks": []}).status_code == 404

	assert vocab_client.post("/api/games/word_rain/complete", headers=headers, json={"score": 2}).status_code == 422
	assert vocab_client.post("/api/games/word_rain/complete", headers=headers, json={"score": 9}).json() == {"xp_awarded": 8}
	assert vocab_client.post("/api/games/nope/complete", headers=headers, json={"score": 9}).status_code == 404
	turn = vocab_client.post("/api/games/word-chain/turn", headers=headers, json={"chain": [], "word": "apple"})
	assert turn.status_code == 200 and turn.json()["reply"]


def test_readability_flags_long_passive_and_adverbs(vocab_client: TestClient) -> None:
	headers = login(vocab_client)
	text = "The report was written by the committee. " + "It really quickly became a very " + "long " * 25 + "sentence."
	result = vocab_client.post("/api/writing/readability", headers=headers, json={"text": text}).json()
	assert result["sentence_count"] == 2 and result["long_sentences"] == 1
	assert result["passive_count"] == 1 and {"really", "quickly"} <= set(result["adverbs"])
	assert sum(result["cefr_counts"].values()) > 0


def _recv(ws, kind: str) -> dict:
	# Bỏ qua các thông điệp opponent_progress xen kẽ cho đến khi gặp loại cần đọc.
	while (message := ws.receive_json())["type"] != kind:
		pass
	return message


def test_speed_quiz_two_players_match_and_result(vocab_client: TestClient) -> None:
	tokens = [login(vocab_client)["Authorization"].split()[1] for _ in range(2)]
	with vocab_client.websocket_connect(f"/api/games/speed-quiz/ws?token={tokens[0]}") as first:
		assert first.receive_json()["type"] == "waiting"
		with vocab_client.websocket_connect(f"/api/games/speed-quiz/ws?token={tokens[1]}") as second:
			start_a, start_b = first.receive_json(), second.receive_json()
			assert start_a["type"] == start_b["type"] == "start" and len(start_a["questions"]) == 5
			assert start_a["questions"] == start_b["questions"] and "answer" not in start_a["questions"][0]
			for q in range(5):
				first.send_json({"type": "answer", "q": q, "choice": "__wrong__"})
				feedback = _recv(first, "feedback")
				assert feedback["correct"] is False
				second.send_json({"type": "answer", "q": q, "choice": feedback["answer"]})
				assert _recv(second, "feedback")["correct"] is True
			loser, winner = _recv(first, "result"), _recv(second, "result")
			assert (loser["result"], winner["result"]) == ("lose", "win")
			assert (winner["you"], winner["opponent"]) == (5, 0) and winner["xp_awarded"] == 12 and loser["xp_awarded"] == 6


def test_speed_quiz_rejects_bad_token(vocab_client: TestClient) -> None:
	import pytest
	from starlette.websockets import WebSocketDisconnect

	with pytest.raises(WebSocketDisconnect):
		with vocab_client.websocket_connect("/api/games/speed-quiz/ws?token=nope"):
			pass


def test_every_passage_parses_into_clean_tokens() -> None:
	for index in range(len(games_service._PASSAGES)):
		tokens, answers = games_service._parse_passage(index)
		assert answers and all(0 <= i < len(tokens) for i in answers)
		assert not any(c in t for t in tokens for c in "[]~") and "->" not in " ".join(tokens)


def test_extension_micro_quiz_and_scope(vocab_client: TestClient) -> None:
	from app.services import wordlist_service

	user = {"email": f"ext_{__import__('uuid').uuid4().hex[:10]}@example.com", "password": "StrongPass123", "target_level": "b1"}
	assert vocab_client.post("/api/auth/register", json=user).status_code == 201
	token = vocab_client.post("/api/auth/login", json={**user, "client_type": "extension"}).json()["access_token"]
	headers = {"Authorization": f"Bearer {token}"}

	quiz = vocab_client.get("/api/extension/quiz", headers=headers).json()
	meanings = {term.lower(): m for t in wordlist_service._topics().values() for term, m, *_ in t["words"]}
	assert len(quiz["options"]) == 4 and meanings[quiz["prompt"].lower()] in quiz["options"]
	wrong = next(o for o in quiz["options"] if o != meanings[quiz["prompt"].lower()])
	assert vocab_client.post("/api/extension/quiz/answer", headers=headers, json={"prompt": quiz["prompt"], "choice": wrong}).json()["xp_awarded"] == 0
	xps = [
		vocab_client.post("/api/extension/quiz/answer", headers=headers, json={"prompt": quiz["prompt"], "choice": meanings[quiz["prompt"].lower()]}).json()["xp_awarded"]
		for _ in range(6)
	]
	assert xps == [3, 3, 3, 3, 3, 0]
	assert vocab_client.post("/api/extension/quiz/answer", headers=headers, json={"prompt": "zzz", "choice": "x"}).status_code == 404
	# Token extension vẫn bị chặn ở route ngoài phạm vi (ví, game).
	assert vocab_client.get("/api/games/quests", headers=headers).status_code == 403
