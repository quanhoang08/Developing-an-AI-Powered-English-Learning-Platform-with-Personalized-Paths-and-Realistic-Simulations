import pytest

from app.services import speech_service
from tests.test_notebook_chat_integration import chat_client, login  # noqa: F401

# Audio thật qua toàn pipeline: Azure TTS tạo file -> upload -> Azure STT -> chunk -> embedding
# Gemini -> pgvector -> chat RAG bằng cả Gemini lẫn Ollama. Không mock bước nào.

SPOKEN_TEXT = (
    "The Eiffel Tower was completed in eighteen eighty nine for the World's Fair in Paris. "
    "It was designed by engineer Gustave Eiffel and stands three hundred and thirty meters tall."
)


@pytest.fixture(scope="module")
def audio_bytes() -> bytes:
    return speech_service.synthesize_azure_speech(SPOKEN_TEXT)


def _upload_audio(client, headers, audio_bytes: bytes) -> dict:
    response = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("lecture.wav", audio_bytes, "application/octet-stream")},
    )
    assert response.status_code == 201
    return response.json()


def test_audio_upload_is_transcribed_and_ready(chat_client, audio_bytes) -> None:
    headers = login(chat_client)
    document = _upload_audio(chat_client, headers, audio_bytes)
    assert document["source_type"] == "audio"
    assert document["status"] == "ready"


@pytest.mark.parametrize("provider", ["gemini", "ollama"])
def test_chat_about_audio_document_with_each_provider(chat_client, audio_bytes, provider) -> None:
    headers = login(chat_client)
    document_id = _upload_audio(chat_client, headers, audio_bytes)["id"]

    asked = chat_client.post(
        f"/api/documents/{document_id}/chat",
        headers=headers,
        json={"message": "Who designed the Eiffel Tower?", "provider": provider},
    )
    assert asked.status_code == 201, asked.text
    assistant = asked.json()["assistant_message"]
    assert "eiffel" in assistant["content"].lower()
    assert len(assistant["sources"]) > 0
