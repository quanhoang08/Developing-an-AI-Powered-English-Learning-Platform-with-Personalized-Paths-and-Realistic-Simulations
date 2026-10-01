import io
import os
import wave

import pytest
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.services import speech_service
from tests.test_notebook_chat_integration import chat_client, login  # noqa: F401

# Speaking thật end-to-end: giọng nói tạo bằng Azure TTS -> Azure STT + Pronunciation
# Assessment (song song) -> Gemini/Ollama chấm ý định/lịch sự + phản hồi -> Azure TTS trả lời.

UTTERANCE = "Hello, I would like to order a cheeseburger and a cola, please."


@pytest.fixture(scope="module")
def learner_wav() -> bytes:
    return speech_service.synthesize_azure_speech(UTTERANCE, "en-US-GuyNeural")


def _silent_wav(seconds: float = 2.0) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buffer.getvalue()


def _restaurant_session(client, headers) -> str:
    scenarios = client.get("/api/speaking/scenarios", headers=headers)
    assert scenarios.status_code == 200
    restaurant = next(item for item in scenarios.json() if "restaurant" in item["title"].lower())
    created = client.post(
        "/api/speaking/sessions", headers=headers, json={"scenario_id": restaurant["id"]}
    )
    assert created.status_code == 201
    return created.json()["session_id"]


def _send_turn(client, headers, session_id: str, audio: bytes, provider: str | None = None):
    params = {"provider": provider} if provider else {}
    return client.post(
        f"/api/speaking/sessions/{session_id}/turns",
        headers=headers,
        params=params,
        files={"audio": ("turn.wav", audio, "audio/wav")},
    )


def test_scenarios_list_and_filter(chat_client) -> None:
    headers = login(chat_client)
    everything = chat_client.get("/api/speaking/scenarios", headers=headers).json()
    assert len(everything) >= 4
    formal = chat_client.get(
        "/api/speaking/scenarios", headers=headers, params={"formality_level": "formal"}
    ).json()
    assert formal and all(item["formality_level"] == "formal" for item in formal)


@pytest.mark.parametrize("provider", ["gemini", "ollama"])
def test_turn_scores_pronunciation_intent_and_replies(chat_client, learner_wav, provider) -> None:
    headers = login(chat_client)
    session_id = _restaurant_session(chat_client, headers)

    response = _send_turn(chat_client, headers, session_id, learner_wav, provider)
    if response.status_code == 429 and "ai_quota_exceeded" in response.text:
        pytest.skip("Gemini hết hạn mức (free tier), không phải lỗi mã")
    assert response.status_code == 201, response.text
    turn = response.json()

    assert "cheeseburger" in turn["user_transcript"].lower() or "burger" in turn["user_transcript"].lower()
    assert turn["stt_provider_used"] == "azure"
    # Nhánh B chấm trên audio gốc: giọng TTS chuẩn phải được điểm cao, không có cờ lỗi.
    assert turn["pronunciation_assessment_failed"] is False
    assert turn["pronunciation_score"] >= 70
    assert turn["pronunciation_advice"]
    # Nhánh A: điểm ý định/lịch sự hợp lệ 0-100 và có phản hồi hội thoại.
    assert 0 <= turn["intent_score"] <= 100 and 0 <= turn["politeness_score"] <= 100
    assert turn["response_text"].strip()
    # Audio phản hồi TTS thật đã được ghi ra file.
    reply_audio = chat_client.get(turn["response_audio_url"], headers=headers)
    assert reply_audio.status_code == 200 and len(reply_audio.content) > 1000

    detail = chat_client.get(f"/api/speaking/sessions/{session_id}", headers=headers).json()
    assert detail["status"] == "in_progress" and len(detail["turns"]) == 1

    second = _send_turn(chat_client, headers, session_id, learner_wav, provider)
    assert second.status_code == 201, second.text
    detail = chat_client.get(f"/api/speaking/sessions/{session_id}", headers=headers).json()
    assert len(detail["turns"]) == 2


def test_silent_audio_is_rejected_without_creating_a_turn(chat_client) -> None:
    headers = login(chat_client)
    session_id = _restaurant_session(chat_client, headers)

    response = _send_turn(chat_client, headers, session_id, _silent_wav())
    assert response.status_code == 422
    assert response.json()["detail"] == "empty_transcription"
    detail = chat_client.get(f"/api/speaking/sessions/{session_id}", headers=headers).json()
    assert detail["turns"] == []


def test_invalid_input_and_ownership(chat_client, learner_wav) -> None:
    owner = login(chat_client)
    session_id = _restaurant_session(chat_client, owner)

    bad_type = chat_client.post(
        f"/api/speaking/sessions/{session_id}/turns",
        headers=owner,
        files={"audio": ("notes.txt", b"hello", "text/plain")},
    )
    assert bad_type.status_code == 400 and bad_type.json()["detail"] == "unsupported_audio_type"

    other = login(chat_client)
    hidden = _send_turn(chat_client, other, session_id, learner_wav)
    assert hidden.status_code == 404 and hidden.json()["detail"] == "session_not_found"

    unknown = chat_client.post(
        "/api/speaking/sessions",
        headers=owner,
        json={"scenario_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert unknown.status_code == 404 and unknown.json()["detail"] == "scenario_not_found"


def test_idle_session_expires_after_30_minutes(chat_client, learner_wav) -> None:
    headers = login(chat_client)
    session_id = _restaurant_session(chat_client, headers)
    engine = create_engine(get_settings().database_url_sync)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE conversation_sessions SET started_at = now() - interval '31 minutes' WHERE id = :id"),
            {"id": session_id},
        )
    engine.dispose()

    expired = _send_turn(chat_client, headers, session_id, learner_wav)
    assert expired.status_code == 409 and expired.json()["detail"] == "session_expired"
    detail = chat_client.get(f"/api/speaking/sessions/{session_id}", headers=headers).json()
    assert detail["status"] == "expired"
