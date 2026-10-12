# Gọi thoại Gemini Live (F22): phần logic không cần gọi Gemini thật (tiết kiệm quota free tier).
from fastapi.testclient import TestClient

from app.main import app
from app.models.speaking import Scenario
from app.services.live_call_service import append_transcript, build_system_prompt


def test_append_transcript_merges_chunks_of_same_speaker():
	transcript: list[dict] = []
	for role, text in [("ai", "Hello"), ("ai", " there!"), ("user", "Hi"), ("user", ""), ("user", " Lumina"), ("ai", "How")]:
		append_transcript(transcript, role, text)
	assert transcript == [
		{"role": "ai", "text": "Hello there!"},
		{"role": "user", "text": "Hi Lumina"},
		{"role": "ai", "text": "How"},
	]


def test_system_prompt_uses_level_and_scenario():
	scene = Scenario(title="Hotel check-in", description="At the front desk.", goal="Get a room", formality_level="formal")
	prompt = build_system_prompt("A2", scene)
	assert "A2" in prompt and "Hotel check-in" in prompt and "Get a room" in prompt and "formal" in prompt
	assert "free conversation" in build_system_prompt(None, None) and "B1" in build_system_prompt(None, None)


def test_live_call_rejects_invalid_token():
	with TestClient(app).websocket_connect("/api/speaking/live") as ws:
		ws.send_json({"token": "not-a-jwt"})
		assert ws.receive_json() == {"type": "error", "code": "invalid_token"}
