import httpx
import pytest

from app.services import speech_service


class _FakeResponse:
    status_code = 200

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_assess_pronunciation_without_scores_is_a_service_error(monkeypatch, tmp_path) -> None:
    # Azure nhận dạng được lời nói nhưng không kèm điểm: phải thành SpeechServiceError (caller bỏ điểm),
    # không phải KeyError làm hỏng cả lượt nói.
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    monkeypatch.setattr(speech_service, "_azure_region_and_key", lambda: ("region", "key"))
    monkeypatch.setattr(speech_service, "ensure_wav", lambda path: path)
    payload = {"RecognitionStatus": "Success", "NBest": [{"Display": "hi", "Words": []}]}
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: _FakeResponse(payload))

    with pytest.raises(speech_service.SpeechServiceError, match="azure_pronunciation_no_scores"):
        speech_service.assess_pronunciation(str(wav))
