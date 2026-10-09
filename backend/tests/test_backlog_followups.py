"""Backlog 4.6 (XP tuần), 5.1 (tự chấm bài giao), 3.7 (báo cáo mẹo), 3.5 (chủ đề), 1.6 (cụm từ lỗi), 2.4 (chỉ số Speaking)."""
import asyncio
import uuid

from fastapi.testclient import TestClient

from app.database import get_db as db_dependency
from app.main import app
from app.services import adaptive_service, ielts_service, reading_service
from app.services.gamification_service import award_activity
from tests.test_social_class import signup
from tests.test_vocab_integration import login, vocab_client  # noqa: F401  (fixture)


def _user_id(client: TestClient, headers: dict) -> uuid.UUID:
	return uuid.UUID(client.get("/api/users/me", headers=headers).json()["id"])


def _in_db(coro_fn) -> None:
	async def run() -> None:
		async for db in app.dependency_overrides[db_dependency]():
			await coro_fn(db)
			await db.commit()

	asyncio.run(run())


def test_weekly_xp_on_leaderboard(vocab_client: TestClient) -> None:
	_, a = signup(vocab_client)
	uid = _user_id(vocab_client, a)

	async def seed(db) -> None:
		await award_activity(db, uid, "writing_submitted")  # 30 XP

	_in_db(seed)
	for period, key in (("all", "total_xp"), ("week", "weekly_xp")):
		row = vocab_client.get("/api/friends/leaderboard", headers=a, params={"period": period}).json()[0]
		assert row[key] == 30 and row["weekly_xp"] == 30
	assert vocab_client.get("/api/friends/leaderboard", headers=a, params={"period": "x"}).status_code == 422


def test_assignment_autograde_by_skill(vocab_client: TestClient) -> None:
	_, teacher = signup(vocab_client)
	_, student = signup(vocab_client)
	room = vocab_client.post("/api/classes", headers=teacher, json={"name": "Auto"}).json()
	cid = room["id"]
	vocab_client.post("/api/classes/join", headers=student, json={"code": room["join_code"]})
	vocab_client.post(f"/api/classes/{cid}/assignments", headers=teacher, json={"title": "Write", "skill": "writing"})
	vocab_client.post(f"/api/classes/{cid}/assignments", headers=teacher, json={"title": "Free"})

	def states(headers) -> dict:
		return {a["title"]: a for a in vocab_client.get(f"/api/classes/{cid}", headers=headers).json()["assignments"]}

	assert states(student)["Write"]["done"] is False and states(student)["Write"]["auto_graded"] is True
	assert states(student)["Free"]["auto_graded"] is False

	sid = _user_id(vocab_client, student)

	async def seed(db) -> None:
		await award_activity(db, sid, "reading_completed")  # sai kỹ năng: không tính
		await award_activity(db, sid, "writing_submitted")

	_in_db(seed)
	assert states(student)["Write"]["done"] is True and states(student)["Free"]["done"] is False
	teacher_view = vocab_client.get(f"/api/classes/{cid}", headers=teacher).json()
	by_title = {a["title"]: a for a in teacher_view["assignments"]}
	assert (by_title["Write"]["done_count"], by_title["Write"]["total_students"]) == (1, 1) and by_title["Free"]["done_count"] == 0
	assert (teacher_view["students"][0]["assignments_done"], teacher_view["students"][0]["assignments_total"]) == (1, 2)


def test_reported_mnemonic_hidden_after_threshold(vocab_client: TestClient) -> None:
	owner, *others = [login(vocab_client) for _ in range(5)]
	term = "Report-" + owner["Authorization"][-8:]
	vocab_client.post("/api/vocab/mnemonics", headers=owner, json={"term": term, "text": "mẹo không phù hợp"})
	mid = vocab_client.get("/api/vocab/mnemonics", headers=owner, params={"term": term}).json()[0]["id"]
	assert vocab_client.post(f"/api/vocab/mnemonics/{mid}/report", headers=owner).status_code == 409  # không tự báo cáo

	def visible(headers) -> int:
		return len(vocab_client.get("/api/vocab/mnemonics", headers=headers, params={"term": term}).json())

	b, c, d, e = others
	assert vocab_client.post(f"/api/vocab/mnemonics/{mid}/report", headers=b).status_code == 204
	assert vocab_client.post(f"/api/vocab/mnemonics/{mid}/report", headers=b).status_code == 204  # idempotent
	assert (visible(b), visible(c)) == (0, 1)  # người báo cáo không thấy lại; người khác vẫn thấy khi chưa đủ ngưỡng
	vocab_client.post(f"/api/vocab/mnemonics/{mid}/report", headers=c)
	assert visible(e) == 1
	vocab_client.post(f"/api/vocab/mnemonics/{mid}/report", headers=d)
	assert visible(e) == 0 and visible(owner) == 1  # đủ 3 báo cáo: ẩn với người khác, chủ mẹo vẫn thấy


def test_vocab_topics_add_without_llm(vocab_client: TestClient) -> None:
	h = login(vocab_client)
	topics = {t["id"]: t for t in vocab_client.get("/api/vocab/topics", headers=h).json()}
	assert {"ff_economy", "ff_health", "ff_environment"} <= set(topics) and not any(w["saved"] for w in topics["ff_economy"]["words"])
	added = vocab_client.post("/api/vocab/topics/ff_economy/add", headers=h)
	assert added.status_code == 200 and len(added.json()) == len(topics["ff_economy"]["words"])
	assert vocab_client.post("/api/vocab/topics/ff_economy/add", headers=h).json() == []
	assert all(w["saved"] for t in vocab_client.get("/api/vocab/topics", headers=h).json() if t["id"] == "ff_economy" for w in t["words"])
	assert vocab_client.post("/api/vocab/topics/nope/add", headers=h).status_code == 404


def test_from_errors_takes_short_speaking_phrases_only(vocab_client: TestClient, monkeypatch) -> None:
	async def fake_lookup(term: str, context: str) -> dict:
		return {"definition": f"nghia {term}", "ipa": None, "example_sentence": "", "synonyms": [], "antonyms": []}

	monkeypatch.setattr(reading_service, "lookup_term", fake_lookup)
	h = login(vocab_client)
	uid = _user_id(vocab_client, h)

	async def seed(db) -> None:
		for natural in ("take a photo", "Take  a photo", "I would really like to take a photo of the lake today"):
			adaptive_service.record_error(db, uid, "vocabulary", {"source": "speaking_literal_translation", "original_text": "make photo", "corrected_text": natural})

	_in_db(seed)
	assert [i["term"] for i in vocab_client.post("/api/vocab/from-errors", headers=h).json()] == ["take a photo"]


def test_speech_summary_aggregates_answers() -> None:
	assert ielts_service.speech_summary([{"filler_count": 2, "lexical_diversity": 0.5}, {"filler_count": 1, "lexical_diversity": 0.7}]) == {"filler_count": 3, "lexical_diversity": 0.6}
	assert ielts_service.speech_summary([{"transcript": "old attempt"}]) == {"filler_count": None, "lexical_diversity": None}


def test_practice_question_replaces_trailing_ai_question(monkeypatch) -> None:
	from app.services import llm_service, speaking_service

	async def fake_question(description: str, learner_text: str, notes: list[str]) -> str:
		assert notes == ['grammar: "I have 20 years old" -> "I am 20 years old"']  # lỗi không có bản sửa bị bỏ
		return "How old is your brother?"

	monkeypatch.setattr(llm_service, "generate_practice_question", fake_question)
	reply = {"response_text": "Nice to meet you! What do you like to do?"}
	asyncio.run(speaking_service._add_practice_question(reply, "class", "hi", ['grammar: "I have 20 years old" -> "I am 20 years old"', 'spelling: "teh"']))
	assert reply["response_text"] == "Nice to meet you! How old is your brother?"

	same = {"response_text": "Great."}
	asyncio.run(speaking_service._add_practice_question(same, "class", "hi", []))  # không có lỗi cũ: giữ nguyên
	assert same["response_text"] == "Great."
