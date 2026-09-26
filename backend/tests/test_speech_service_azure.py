import pytest

from app.core.config import get_settings
from app.services import speech_service

# Gọi Azure Speech thật (TTS -> STT khứ hồi), không mock — bỏ qua nếu chưa có key.
pytestmark = pytest.mark.skipif(
    not get_settings().azure_speech_key, reason="AZURE_SPEECH_KEY chưa cấu hình"
)

SENTENCE = "The Eiffel Tower was designed by Gustave Eiffel and stands three hundred meters tall."


@pytest.fixture(scope="module")
def spoken_wav(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("azure") / "sentence.wav"
    path.write_bytes(speech_service.synthesize_azure_speech(SENTENCE))
    return str(path)


def test_tts_returns_pcm_wav(spoken_wav: str) -> None:
    with open(spoken_wav, "rb") as handle:
        assert handle.read(4) == b"RIFF"


def test_stt_roundtrip_returns_text_and_word_timestamps(spoken_wav: str) -> None:
    result = speech_service.transcribe_audio(spoken_wav)
    lowered = result.text.lower()
    assert "eiffel" in lowered and "gustave" in lowered
    assert result.duration_ms > 3000
    assert len(result.words) >= 10
    # Timestamp cấp từ phải tăng dần và không âm — nền tảng cho transcript_segments.
    starts = [word.start_ms for word in result.words]
    assert starts == sorted(starts) and starts[0] >= 0
    assert all(word.end_ms >= word.start_ms for word in result.words)


def test_stt_rejects_non_audio(tmp_path) -> None:
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"this is not audio")
    with pytest.raises(speech_service.SpeechServiceError):
        speech_service.transcribe_audio(str(bad))


def test_missing_key_raises_clear_error(monkeypatch, spoken_wav: str) -> None:
    monkeypatch.setattr(get_settings(), "azure_speech_key", "")
    with pytest.raises(speech_service.SpeechServiceError, match="azure_speech_not_configured"):
        speech_service.transcribe_audio(spoken_wav)
