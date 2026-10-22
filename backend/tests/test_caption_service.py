import asyncio

from app.services import caption_service
from app.services.caption_service import LocalEngine, SonioxEngine, _pick_engine, _SonioxStream


def _stream():
	"""_SonioxStream không kết nối mạng khi dựng bằng __new__; chỉ thử phần phân tích token."""
	sent: list[dict] = []

	async def send(message: dict) -> None:
		sent.append(message)

	stream = _SonioxStream.__new__(_SonioxStream)
	stream.source, stream.send = caption_service.SYSTEM, send
	stream.caption_id, stream.text, stream.translation = 1, "", ""
	return stream, sent


def _tok(text: str, final: bool, translation: bool = False) -> dict:
	return {"text": text, "is_final": final, **({"translation_status": "translation"} if translation else {})}


def test_soniox_interim_then_endpoint_closes_the_caption():
	stream, sent = _stream()

	async def run() -> None:
		await stream._handle({"tokens": [_tok("Hello ", True), _tok("wor", False), _tok("Xin chào", False, True)]})
		await stream._handle({"tokens": [_tok("world.", True), _tok("Xin chào thế giới.", True, True), _tok("<end>", True)]})
		await stream._handle({"tokens": [_tok("Next", False)]})

	asyncio.run(run())
	assert [(m["id"], m["text"], m["translation"], m["final"]) for m in sent] == [
		(1, "Hello wor", "Xin chào", False),
		(1, "Hello world.", "Xin chào thế giới.", True),
		(2, "Next", None, False),
	]
	assert all(m["source"] == "system" for m in sent)


def test_soniox_error_payload_raises_so_the_session_falls_back():
	stream, _ = _stream()
	try:
		asyncio.run(stream._handle({"error_code": 402, "error_message": "quota"}))
	except RuntimeError as error:
		assert "402" in str(error)
	else:
		raise AssertionError("expected RuntimeError")


def _fake_ollama(monkeypatch, replies: list[str]) -> list[str]:
	calls: list[str] = []

	class Client:
		def __init__(self, **_kwargs) -> None:
			pass

		async def chat(self, **_kwargs):
			calls.append("chat")
			return {"message": {"content": replies[len(calls) - 1]}}

	monkeypatch.setattr(caption_service.ollama, "AsyncClient", Client)
	return calls


def test_translation_retries_when_model_mixes_in_chinese(monkeypatch):
	calls = _fake_ollama(monkeypatch, ["Cảm ơn bạn.今天能与你们", "Cảm ơn bạn."])
	assert asyncio.run(caption_service.translate_to_vi("Thank you.")) == "Cảm ơn bạn."
	assert len(calls) == 2


def test_translation_gives_up_when_model_keeps_mixing_in_chinese(monkeypatch):
	_fake_ollama(monkeypatch, ["谢谢你", "谢谢你"])
	try:
		asyncio.run(caption_service.translate_to_vi("Thank you."))
	except ValueError as error:
		assert "translation_not_vietnamese" in str(error)
	else:
		raise AssertionError("expected ValueError")


def test_engine_choice_follows_key_and_provider(monkeypatch):
	class Settings:
		soniox_api_key = ""

	monkeypatch.setattr(caption_service, "get_settings", lambda: Settings)
	assert _pick_engine("auto") is LocalEngine
	assert _pick_engine("local") is LocalEngine
	Settings.soniox_api_key = "key"
	assert _pick_engine("auto") is SonioxEngine
	assert _pick_engine("local") is LocalEngine
