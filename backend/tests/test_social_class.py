import io
import uuid
from datetime import date

from fastapi.testclient import TestClient

from app.services import speech_service
from tests.test_vocab_integration import vocab_client  # noqa: F401  (fixture)


def signup(client: TestClient) -> tuple[str, dict[str, str]]:
	email = f"soc_{uuid.uuid4().hex[:12]}@example.com"
	assert client.post("/api/auth/register", json={"email": email, "password": "StrongPass123", "target_level": "b1"}).status_code == 201
	token = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"}).json()["access_token"]
	return email, {"Authorization": f"Bearer {token}"}


def test_voice_diary_round_trip(vocab_client: TestClient, monkeypatch) -> None:
	monkeypatch.setattr(speech_service, "transcribe_with_fallback", lambda path: ("I went to school today and met friends", "azure"))
	_, h = signup(vocab_client)
	wav = {"audio": ("d.wav", io.BytesIO(b"RIFFxxxx"), "audio/wav")}
	r = vocab_client.post("/api/diary", params={"duration_seconds": 10}, headers=h, files=wav)
	assert r.status_code == 201 and r.json()["words_per_minute"] == 48
	assert vocab_client.post("/api/diary", params={"duration_seconds": 90}, headers=h, files={"audio": ("d.wav", io.BytesIO(b"x"), "audio/wav")}).status_code == 422
	entry_id = r.json()["id"]
	assert len(vocab_client.get("/api/diary", headers=h).json()) == 1
	assert vocab_client.get(f"/api/diary/{entry_id}/audio", headers=h).content == b"RIFFxxxx"
	_, other = signup(vocab_client)
	assert vocab_client.get(f"/api/diary/{entry_id}/audio", headers=other).status_code == 404
	assert vocab_client.delete(f"/api/diary/{entry_id}", headers=h).status_code == 204
	assert vocab_client.get("/api/diary", headers=h).json() == []


def test_friends_and_leaderboard(vocab_client: TestClient) -> None:
	_, a = signup(vocab_client)
	b_mail, b = signup(vocab_client)
	# Email không tồn tại và email có thật đều nhận cùng một phản hồi.
	assert vocab_client.post("/api/friends/requests", headers=a, json={"email": "nobody@example.com"}).status_code == 202
	assert vocab_client.post("/api/friends/requests", headers=a, json={"email": b_mail}).status_code == 202
	incoming = vocab_client.get("/api/friends", headers=b).json()["incoming"]
	assert len(incoming) == 1
	fid = incoming[0]["friendship_id"]
	assert vocab_client.post(f"/api/friends/{fid}/accept", headers=a).status_code == 404  # người gửi không tự chấp nhận
	assert vocab_client.post(f"/api/friends/{fid}/accept", headers=b).status_code == 204
	board = vocab_client.get("/api/friends/leaderboard", headers=a).json()
	assert len(board) == 2 and sum(r["is_me"] for r in board) == 1 and [r["rank"] for r in board] == [1, 2]
	assert vocab_client.delete(f"/api/friends/{fid}", headers=a).status_code == 204
	assert len(vocab_client.get("/api/friends/leaderboard", headers=a).json()) == 1


def test_classroom_flow(vocab_client: TestClient) -> None:
	_, teacher = signup(vocab_client)
	_, student = signup(vocab_client)
	_, outsider = signup(vocab_client)
	room = vocab_client.post("/api/classes", headers=teacher, json={"name": "Class 9A"}).json()
	assert len(room["join_code"]) == 6
	assert vocab_client.post("/api/classes/join", headers=student, json={"code": "ZZZZZZ"}).status_code == 404
	assert vocab_client.post("/api/classes/join", headers=student, json={"code": room["join_code"].lower()}).status_code == 200
	cid = room["id"]
	assert vocab_client.get(f"/api/classes/{cid}", headers=outsider).status_code == 404
	assert vocab_client.post(f"/api/classes/{cid}/assignments", headers=student, json={"title": "x"}).status_code == 403
	made = vocab_client.post(
		f"/api/classes/{cid}/assignments", headers=teacher, json={"title": "Read unit 3", "skill": "reading", "due_date": "2030-01-01"}
	)
	assert made.status_code == 201
	as_teacher = vocab_client.get(f"/api/classes/{cid}", headers=teacher).json()
	assert as_teacher["join_code"] and len(as_teacher["students"]) == 1 and as_teacher["assignments"][0]["title"] == "Read unit 3"
	as_student = vocab_client.get(f"/api/classes/{cid}", headers=student).json()
	assert as_student["join_code"] is None and as_student["students"] == [] and len(as_student["assignments"]) == 1
	mine = vocab_client.get("/api/classes", headers=student).json()
	assert [c["name"] for c in mine["joined"]] == ["Class 9A"]
	student_id = as_teacher["students"][0]["user_id"]
	assert vocab_client.delete(f"/api/classes/{cid}/members/{student_id}", headers=outsider).status_code == 404
	assert vocab_client.delete(f"/api/classes/{cid}/members/{student_id}", headers=student).status_code == 204  # tự rời lớp
	assert vocab_client.delete(f"/api/classes/{cid}", headers=teacher).status_code == 204
