import os

import pytest

from app.services import speech_service
from tests.test_notebook_chat_integration import (  # noqa: F401
    DOCUMENT_TEXT,
    chat_client,
    login,
    make_docx_bytes,
)

# Podcast thật end-to-end: audio gốc (Azure TTS làm nguồn) và .docx (Gemini biên tập ->
# Azure TTS -> Azure STT lấy timestamp cấp từ) -> transcript -> Dictation trên chính podcast đó.

SPOKEN_TEXT = (
    "The Great Wall of China was built over many centuries by several Chinese dynasties. "
    "It stretches for more than twenty one thousand kilometers across northern China."
)


def _upload(client, headers, name: str, content: bytes) -> str:
    response = client.post(
        "/api/documents", headers=headers, files={"file": (name, content, "application/octet-stream")}
    )
    assert response.status_code == 201
    assert response.json()["status"] == "ready"
    return response.json()["id"]


def _assert_transcript_is_word_level(client, headers, podcast_id: str) -> list[dict]:
    response = client.get(f"/api/listening/podcasts/{podcast_id}/transcript", headers=headers)
    assert response.status_code == 200
    segments = response.json()["segments"]
    assert len(segments) >= 10
    starts = [item["start_ms"] for item in segments]
    assert starts == sorted(starts)
    assert all(item["end_ms"] >= item["start_ms"] for item in segments)
    return segments


def test_podcast_from_audio_keeps_original_file_and_supports_dictation(chat_client) -> None:
    headers = login(chat_client)
    wav = speech_service.synthesize_azure_speech(SPOKEN_TEXT)
    document_id = _upload(chat_client, headers, "wall.wav", wav)

    created = chat_client.post(
        "/api/listening/podcasts", headers=headers, json={"document_id": document_id}
    )
    assert created.status_code == 201, created.text
    podcast = created.json()
    assert podcast["status"] == "ready"
    # Audio gốc: audio_url trỏ đúng file đã upload, không sinh TTS mới (mục 1.6).
    document_file = chat_client.get(f"/api/documents/{document_id}", headers=headers).json()
    assert os.path.basename(podcast["audio_url"]).startswith(document_id)

    segments = _assert_transcript_is_word_level(chat_client, headers, podcast["id"])
    assert "great" in " ".join(item["text"].lower() for item in segments)
    assert document_file["id"] == document_id

    fetched = chat_client.get(f"/api/listening/podcasts/{podcast['id']}", headers=headers)
    assert fetched.status_code == 200 and fetched.json()["status"] == "ready"

    # Dictation dùng được ngay trên podcast vừa tạo (cắt WAV thật theo timestamp Azure).
    dictation = chat_client.post(
        "/api/listening/dictation", headers=headers, json={"podcast_id": podcast["id"]}
    )
    assert dictation.status_code == 201, dictation.text
    submitted = chat_client.post(
        f"/api/listening/dictation/{dictation.json()['attempt_id']}/submit",
        headers=headers,
        json={"transcribed_text": " ".join(item["text"] for item in segments)},
    )
    assert submitted.status_code == 200
    assert submitted.json()["score"] >= 90


def test_podcast_from_docx_generates_tts_audio_and_transcript(chat_client) -> None:
    headers = login(chat_client)
    document_id = _upload(chat_client, headers, "landmarks.docx", make_docx_bytes(DOCUMENT_TEXT))

    created = chat_client.post(
        "/api/listening/podcasts", headers=headers, json={"document_id": document_id}
    )
    assert created.status_code == 201, created.text
    podcast = created.json()
    assert podcast["status"] == "ready"
    assert podcast["audio_url"].endswith(".wav") and "podcast_" in podcast["audio_url"]
    assert podcast["duration_seconds"] > 5
    _assert_transcript_is_word_level(chat_client, headers, podcast["id"])


def test_podcast_ownership_and_missing_document(chat_client) -> None:
    owner = login(chat_client)
    document_id = _upload(chat_client, owner, "landmarks.docx", make_docx_bytes(DOCUMENT_TEXT))
    other = login(chat_client)

    hidden = chat_client.post(
        "/api/listening/podcasts", headers=other, json={"document_id": document_id}
    )
    assert hidden.status_code == 404 and hidden.json()["detail"] == "document_not_found"

    missing = chat_client.get(
        "/api/listening/podcasts/00000000-0000-0000-0000-000000000000/transcript", headers=owner
    )
    assert missing.status_code == 404
