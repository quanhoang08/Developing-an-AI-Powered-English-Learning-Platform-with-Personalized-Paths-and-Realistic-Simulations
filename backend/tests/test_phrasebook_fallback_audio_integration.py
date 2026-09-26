import pytest

from app.services import speech_service
from tests.test_notebook_chat_integration import chat_client, login  # noqa: F401

# Phrasebook/slang, STT dự phòng Gemini (khi Azure lỗi) và các endpoint phục vụ audio cho
# frontend — tất cả chạy với DB/Azure/Gemini thật, chỉ ép Azure STT lỗi bằng monkeypatch
# để kiểm tra đường dự phòng (không thể "gây lỗi" Azure thật một cách ổn định).

UTTERANCE = "Hello, I would like to order a cheeseburger and a cola, please."


@pytest.fixture(scope="module")
def learner_wav() -> bytes:
    return speech_service.synthesize_azure_speech(UTTERANCE, "en-US-GuyNeural")


def _first_slang(client, headers, **params) -> dict:
    response = client.get("/api/speaking/slang", headers=headers, params=params)
    assert response.status_code == 200
    return response.json()


def _new_session(client, headers) -> str:
    scenarios = client.get("/api/speaking/scenarios", headers=headers).json()
    restaurant = next(item for item in scenarios if "restaurant" in item["title"].lower())
    return client.post(
        "/api/speaking/sessions", headers=headers, json={"scenario_id": restaurant["id"]}
    ).json()["session_id"]


def test_slang_library_has_sources_and_filters(chat_client) -> None:
    headers = login(chat_client)
    phrases = _first_slang(chat_client, headers)
    assert len(phrases) >= 45
    # Mục 4.3: 100% bản ghi có nguồn tham chiếu không rỗng.
    assert all(item["source_reference"].strip() for item in phrases)
    assert {item["formality_level"] for item in phrases} == {"casual", "neutral", "formal"}
    formal = _first_slang(chat_client, headers, formality_level="formal")
    assert formal and all(item["formality_level"] == "formal" for item in formal)
    restaurant = _first_slang(chat_client, headers, topic="restaurant")
    assert restaurant and all("restaurant" in item["topic_tags"] for item in restaurant)


def test_phrasebook_save_from_library_snapshot_and_dedupe(chat_client) -> None:
    headers = login(chat_client)
    phrase = _first_slang(chat_client, headers, formality_level="casual")[0]

    saved = chat_client.post(
        "/api/speaking/phrasebook", headers=headers, json={"slang_phrase_id": phrase["id"]}
    )
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body["phrase_text"] == phrase["phrase_text"]
    assert body["meaning"] == phrase["meaning"]
    assert body["source_reference"] == phrase["source_reference"]

    # Lưu lại cùng cụm: trả bản ghi cũ, không nhân đôi.
    again = chat_client.post(
        "/api/speaking/phrasebook", headers=headers, json={"slang_phrase_id": phrase["id"]}
    )
    assert again.json()["id"] == body["id"]

    snapshot = chat_client.post(
        "/api/speaking/phrasebook",
        headers=headers,
        json={"phrase_text": "a sweet deal", "meaning": "a very good bargain", "example_sentence": "That price is a sweet deal."},
    )
    assert snapshot.status_code == 201
    assert snapshot.json()["slang_phrase_id"] is None
    assert snapshot.json()["meaning"] == "a very good bargain"

    listed = chat_client.get("/api/speaking/phrasebook", headers=headers).json()
    assert {item["phrase_text"] for item in listed} == {phrase["phrase_text"], "a sweet deal"}
    by_formality = chat_client.get(
        "/api/speaking/phrasebook", headers=headers, params={"formality_level": "casual"}
    ).json()
    assert [item["phrase_text"] for item in by_formality] == [phrase["phrase_text"]]

    # Sổ tay riêng từng người dùng.
    assert chat_client.get("/api/speaking/phrasebook", headers=login(chat_client)).json() == []


def test_phrasebook_validation_errors(chat_client) -> None:
    headers = login(chat_client)
    empty = chat_client.post("/api/speaking/phrasebook", headers=headers, json={})
    assert empty.status_code == 400 and empty.json()["detail"] == "phrase_data_missing"
    unknown = chat_client.post(
        "/api/speaking/phrasebook",
        headers=headers,
        json={"slang_phrase_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert unknown.status_code == 404 and unknown.json()["detail"] == "slang_phrase_not_found"
    foreign_turn = chat_client.post(
        "/api/speaking/phrasebook",
        headers=headers,
        json={"phrase_text": "x", "conversation_turn_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert foreign_turn.status_code == 404 and foreign_turn.json()["detail"] == "turn_not_found"


def test_stt_falls_back_to_gemini_when_azure_fails(chat_client, learner_wav, monkeypatch, tmp_path) -> None:
    def azure_down(*args, **kwargs):
        raise speech_service.SpeechServiceError("azure_stt_unreachable")

    monkeypatch.setattr(speech_service, "transcribe_audio", azure_down)

    wav_path = tmp_path / "learner.wav"
    wav_path.write_bytes(learner_wav)
    text, provider = speech_service.transcribe_with_fallback(str(wav_path))
    assert provider == "gemini" and "cheeseburger" in text.lower()

    # Toàn bộ lượt Speaking vẫn chạy được, ghi đúng provider đã dùng (mục 1.6).
    headers = login(chat_client)
    session_id = _new_session(chat_client, headers)
    response = chat_client.post(
        f"/api/speaking/sessions/{session_id}/turns",
        headers=headers,
        files={"audio": ("turn.wav", learner_wav, "audio/wav")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["stt_provider_used"] == "gemini"
    assert "burger" in response.json()["user_transcript"].lower()


def test_speaking_reply_audio_is_served_only_to_owner(chat_client, learner_wav) -> None:
    owner = login(chat_client)
    session_id = _new_session(chat_client, owner)
    turn = chat_client.post(
        f"/api/speaking/sessions/{session_id}/turns",
        headers=owner,
        files={"audio": ("turn.wav", learner_wav, "audio/wav")},
    ).json()

    audio = chat_client.get(f"/api/speaking/turns/{turn['turn_id']}/audio", headers=owner)
    assert audio.status_code == 200 and audio.content[:4] == b"RIFF"
    assert audio.headers["content-type"].startswith("audio/")

    other = chat_client.get(f"/api/speaking/turns/{turn['turn_id']}/audio", headers=login(chat_client))
    assert other.status_code == 404

    # Lưu 1 cụm gợi ý từ chính lượt này vào sổ tay.
    saved = chat_client.post(
        "/api/speaking/phrasebook",
        headers=owner,
        json={"phrase_text": "I'd like to order", "conversation_turn_id": turn["turn_id"]},
    )
    assert saved.status_code == 201 and saved.json()["conversation_turn_id"] == turn["turn_id"]


def test_podcast_list_and_audio_endpoints(chat_client, learner_wav) -> None:
    headers = login(chat_client)
    document_id = chat_client.post(
        "/api/documents", headers=headers, files={"file": ("order.wav", learner_wav, "application/octet-stream")}
    ).json()["id"]
    podcast = chat_client.post(
        "/api/listening/podcasts", headers=headers, json={"document_id": document_id}
    ).json()

    listed = chat_client.get("/api/listening/podcasts", headers=headers).json()
    assert [item["id"] for item in listed] == [podcast["id"]]
    assert listed[0]["title"] == "order" and listed[0]["status"] == "ready"

    audio = chat_client.get(f"/api/listening/podcasts/{podcast['id']}/audio", headers=headers)
    assert audio.status_code == 200 and audio.content == learner_wav
    assert chat_client.get(
        f"/api/listening/podcasts/{podcast['id']}/audio", headers=login(chat_client)
    ).status_code == 404

    attempt = chat_client.post(
        "/api/listening/dictation", headers=headers, json={"podcast_id": podcast["id"]}
    ).json()
    segment = chat_client.get(f"/api/listening/dictation/{attempt['attempt_id']}/audio", headers=headers)
    assert segment.status_code == 200 and segment.content[:4] == b"RIFF"
