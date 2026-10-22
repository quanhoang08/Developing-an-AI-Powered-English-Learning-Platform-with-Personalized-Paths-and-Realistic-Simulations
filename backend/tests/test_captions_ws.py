import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.main import app
from app.services import caption_service

PCM = bytes(640)  # 20 ms
WS_PATHS = ["/api/speaking/captions", "/api/extension/captions"]


class FakeEngine:
	"""Engine giả: mỗi chunk nhận được trả về 1 phụ đề, không cần model hay mạng."""

	name = "fake"
	instances: list = []
	start_error: Exception | None = None

	def __init__(self, send) -> None:
		self.send = send
		self.failed = None
		self.fed: list[tuple[int, int]] = []
		self.closed = False
		FakeEngine.instances.append(self)

	async def start(self) -> None:
		if FakeEngine.start_error:
			raise FakeEngine.start_error

	async def feed(self, source: int, pcm: bytes) -> None:
		self.fed.append((source, len(pcm)))
		await self.send({"type": "caption", "source": "system", "id": len(self.fed), "text": f"chunk {len(self.fed)}", "translation": None, "final": True})

	async def close(self) -> None:
		self.closed = True


class FakeSoniox(FakeEngine):
	name = "soniox"

	async def feed(self, source: int, pcm: bytes) -> None:
		await super().feed(source, pcm)
		self.failed = RuntimeError("soniox 402")  # như khi Soniox báo hết credit


class FakeLocal(FakeEngine):
	name = "local"


@pytest.fixture(autouse=True)
def reset_fakes():
	FakeEngine.instances = []
	FakeEngine.start_error = None
	yield
	app.dependency_overrides.clear()


@pytest.fixture
def client():
	with TestClient(app) as test_client:
		yield test_client


def _auth_ok(monkeypatch, engine_class=FakeEngine) -> None:
	async def authenticate(_db, _hello):
		return object(), None

	monkeypatch.setattr(caption_service, "_authenticate", authenticate)
	monkeypatch.setattr(caption_service, "_pick_engine", lambda _provider: engine_class)


def _drain(ws) -> list[dict]:
	"""Đọc tới khi server đóng; trả về các tin JSON."""
	messages = []
	while True:
		try:
			messages.append(ws.receive_json())
		except (WebSocketDisconnect, RuntimeError):
			return messages
		if messages[-1].get("type") == "ended":
			return messages


@pytest.mark.parametrize("path", WS_PATHS)
def test_invalid_token_is_rejected(client, path):
	with client.websocket_connect(path) as ws:
		ws.send_json({"token": "not-a-jwt"})
		assert ws.receive_json() == {"type": "error", "code": "invalid_token"}


@pytest.mark.parametrize("hello", [[], "text", 5, None])
def test_non_object_hello_is_treated_as_missing_token(client, hello):
	with client.websocket_connect(WS_PATHS[0]) as ws:
		ws.send_json(hello)
		assert ws.receive_json()["code"] == "invalid_token"


def test_token_for_unknown_user_is_rejected(client):
	with client.websocket_connect(WS_PATHS[0]) as ws:
		ws.send_json({"token": create_access_token("00000000-0000-0000-0000-000000000000")})
		assert ws.receive_json()["code"] == "invalid_token"


def test_hello_that_is_not_json_closes_the_socket(client):
	with client.websocket_connect(WS_PATHS[0]) as ws:
		ws.send_text("this is not json")
		with pytest.raises(WebSocketDisconnect):
			ws.receive_json()


def test_hello_timeout_closes_the_socket(client, monkeypatch):
	monkeypatch.setattr(caption_service, "_HELLO_TIMEOUT_SECONDS", 0.2)
	with client.websocket_connect(WS_PATHS[0]) as ws:
		with pytest.raises(WebSocketDisconnect):
			ws.receive_json()


def test_soniox_requested_without_key_reports_not_configured(client, monkeypatch):
	async def authenticate(_db, _hello):
		return object(), None

	class NoKey:
		soniox_api_key = ""

	monkeypatch.setattr(caption_service, "_authenticate", authenticate)
	monkeypatch.setattr(caption_service, "get_settings", lambda: NoKey)
	with client.websocket_connect(WS_PATHS[0]) as ws:
		ws.send_json({"token": "x", "provider": "soniox"})
		assert ws.receive_json() == {"type": "error", "code": "captions_not_configured"}


@pytest.mark.parametrize("path", WS_PATHS)
def test_audio_in_caption_out_then_end(client, monkeypatch, path):
	_auth_ok(monkeypatch)
	with client.websocket_connect(path) as ws:
		ws.send_json({"token": "x"})
		assert ws.receive_json()["type"] == "ready"
		ws.send_bytes(b"\x01" + PCM)  # âm thanh hệ thống/tab
		assert ws.receive_json()["text"] == "chunk 1"
		ws.send_bytes(b"\x00" + PCM)  # mic (qua cổng chống vọng)
		assert ws.receive_json()["text"] == "chunk 2"
		ws.send_json({"type": "end"})
		assert _drain(ws)[-1] == {"type": "ended"}
	assert FakeEngine.instances[0].closed
	assert [source for source, _ in FakeEngine.instances[0].fed] == [1, 0]


def test_malformed_frames_are_ignored_not_fatal(client, monkeypatch):
	_auth_ok(monkeypatch)
	with client.websocket_connect(WS_PATHS[0]) as ws:
		ws.send_json({"token": "x"})
		ws.receive_json()  # ready
		ws.send_bytes(b"")  # rỗng
		ws.send_bytes(b"\x01")  # chỉ có byte nguồn, không có âm thanh
		ws.send_bytes(b"\x07" + PCM)  # nguồn không tồn tại
		ws.send_bytes(b"\x01" + bytes(64 * 1024 + 10))  # khung quá lớn
		ws.send_text("not json")  # tin nhắn chữ không phải JSON
		ws.send_json({"type": "something-else"})
		ws.send_bytes(b"\x01" + PCM)  # khung hợp lệ vẫn được xử lý
		assert ws.receive_json()["text"] == "chunk 1"
		ws.send_json({"type": "end"})
		_drain(ws)
	assert len(FakeEngine.instances[0].fed) == 1


def test_odd_length_audio_does_not_crash(client, monkeypatch):
	_auth_ok(monkeypatch)
	with client.websocket_connect(WS_PATHS[0]) as ws:
		ws.send_json({"token": "x"})
		ws.receive_json()
		ws.send_bytes(b"\x00" + bytes(641))  # số byte lẻ
		assert ws.receive_json()["type"] == "caption"
		ws.send_json({"type": "end"})
		_drain(ws)


def test_client_disconnect_closes_the_engine(client, monkeypatch):
	_auth_ok(monkeypatch)
	with client.websocket_connect(WS_PATHS[0]) as ws:
		ws.send_json({"token": "x"})
		ws.receive_json()
	# thoát khối with = trình duyệt đóng kết nối giữa chừng
	assert FakeEngine.instances[0].closed


def test_engine_start_failure_reports_models_unavailable(client, monkeypatch):
	_auth_ok(monkeypatch)
	FakeEngine.start_error = RuntimeError("download failed")
	with client.websocket_connect(WS_PATHS[0]) as ws:
		ws.send_json({"token": "x"})
		messages = _drain(ws)
	assert messages[0] == {"type": "error", "code": "local_models_unavailable"}
	assert messages[-1] == {"type": "ended"}


def test_soniox_failure_falls_back_to_local_and_keeps_captioning(client, monkeypatch):
	_auth_ok(monkeypatch, FakeSoniox)
	monkeypatch.setattr(caption_service, "LocalEngine", FakeLocal)
	with client.websocket_connect(WS_PATHS[0]) as ws:
		ws.send_json({"token": "x"})
		assert ws.receive_json() == {"type": "ready", "engine": "soniox", "max_seconds": 600}
		ws.send_bytes(b"\x01" + PCM)
		assert ws.receive_json()["text"] == "chunk 1"  # Soniox xử lý chunk này rồi báo lỗi
		ws.send_bytes(b"\x01" + PCM)  # chunk kế tiếp kích hoạt đường lui
		assert ws.receive_json() == {"type": "engine", "name": "local", "reason": "soniox_failed"}
		assert ws.receive_json()["text"] == "chunk 1"  # engine local tiếp tục từ đây
		ws.send_json({"type": "end"})
		_drain(ws)
	soniox, local = FakeEngine.instances
	assert soniox.closed and local.closed


def test_fallback_that_cannot_start_local_reports_models_unavailable(client, monkeypatch):
	_auth_ok(monkeypatch, FakeSoniox)

	class BrokenLocal(FakeLocal):
		async def start(self) -> None:
			raise RuntimeError("no models")

	monkeypatch.setattr(caption_service, "LocalEngine", BrokenLocal)
	with client.websocket_connect(WS_PATHS[0]) as ws:
		ws.send_json({"token": "x"})
		ws.receive_json()
		ws.send_bytes(b"\x01" + PCM)
		ws.receive_json()
		ws.send_bytes(b"\x01" + PCM)
		messages = _drain(ws)
	assert {"type": "error", "code": "local_models_unavailable"} in messages


# ---------- POST /api/extension/translate ----------


def _as_user() -> None:
	app.dependency_overrides[get_current_user] = lambda: object()


def test_translate_requires_login(client):
	assert client.post("/api/extension/translate", json={"text": "hi"}).status_code == 401


@pytest.mark.parametrize("text", ["", "x" * 301])
def test_translate_rejects_empty_and_too_long_text(client, text):
	_as_user()
	assert client.post("/api/extension/translate", json={"text": text}).status_code == 422


def test_translate_rejects_missing_body_field(client):
	_as_user()
	assert client.post("/api/extension/translate", json={}).status_code == 422


def test_translate_returns_the_translation(client, monkeypatch):
	_as_user()

	async def translate(text):
		return f"vi: {text}"

	monkeypatch.setattr(caption_service, "translate_to_vi", translate)
	response = client.post("/api/extension/translate", json={"text": "Good morning"})
	assert response.status_code == 200
	assert response.json() == {"translation": "vi: Good morning"}


def test_translate_accepts_the_300_character_limit(client, monkeypatch):
	_as_user()

	async def translate(text):
		return "ok"

	monkeypatch.setattr(caption_service, "translate_to_vi", translate)
	assert client.post("/api/extension/translate", json={"text": "x" * 300}).status_code == 200


@pytest.mark.parametrize("error", [RuntimeError("ollama down"), ValueError("translation_not_vietnamese")])
def test_translate_failure_is_503_so_the_extension_can_fall_back(client, monkeypatch, error):
	_as_user()

	async def translate(_text):
		raise error

	monkeypatch.setattr(caption_service, "translate_to_vi", translate)
	response = client.post("/api/extension/translate", json={"text": "hi"})
	assert response.status_code == 503
	assert response.json()["detail"] == "translate_unavailable"


def test_extension_token_is_not_blocked_by_scope_on_translate(client):
	token = create_access_token("00000000-0000-0000-0000-000000000000", client_type="extension")
	response = client.post("/api/extension/translate", json={"text": "hi"}, headers={"Authorization": f"Bearer {token}"})
	assert response.status_code != 403  # 401 vì user không tồn tại, không phải bị chặn phạm vi


def test_extension_token_is_still_blocked_from_other_routes(client):
	token = create_access_token("00000000-0000-0000-0000-000000000000", client_type="extension")
	response = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
	assert response.status_code == 403
