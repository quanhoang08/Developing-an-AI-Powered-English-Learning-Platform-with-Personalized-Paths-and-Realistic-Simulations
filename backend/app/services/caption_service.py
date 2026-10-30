# Phụ đề trực tiếp + dịch sang tiếng Việt: học tiếng Anh qua video/cuộc họp đang phát (âm thanh tab/hệ thống) và/hoặc micro.
# Hai engine cùng giao diện (start/feed/close), chọn theo provider:
#   - "soniox": Soniox real-time (STT + dịch một chiều sang tiếng Việt trên cùng 1 WebSocket, có kết quả tạm thời). Cần SONIOX_API_KEY.
#   - "local":  EnergyVad + faster-whisper (dùng chung model với gọi thoại local) + Ollama dịch; không cần key, trễ cao hơn, chỉ có kết quả cuối.
# "auto" (mặc định) = soniox nếu có key, không thì local. Soniox đứt/hết quota giữa chừng thì phiên tự lùi về local (đường lui).
# Mic đi qua EchoGate trước khi vào engine nên không đeo tai nghe cũng không bị nhận dạng đôi.
#
# Giao thức với trình duyệt:
#   client -> server: tin đầu JSON {"token", "provider"?: "auto"|"soniox"|"local"}; sau đó frame nhị phân = 1 byte nguồn
#                     (0 = mic, 1 = âm thanh hệ thống) + PCM16 16kHz mono; JSON {"type": "end"} để dừng.
#   server -> client: JSON {"type": "ready" (engine, max_seconds) | "caption" (source, id, text, translation, final) |
#                     "engine" (name, reason) khi lùi về local | "error" (code) | "ended"}.
# Không lưu DB: phụ đề là luồng tạm thời để xem, không có bảng/migration.
import asyncio
import contextlib
import json
import logging
import re

import ollama
import websockets
from fastapi import WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.database import get_session_factory
from app.services import local_call_service
from app.services.echo_gate import EchoGate
from app.services.live_call_service import MAX_AUDIO_FRAME_BYTES, MAX_CALL_SECONDS, _authenticate

logger = logging.getLogger(__name__)

MIC, SYSTEM = 0, 1
_SOURCE_NAMES = {MIC: "mic", SYSTEM: "system"}
_SONIOX_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
_SONIOX_QUEUE_CHUNKS = 250  # ~5 giây; đầy thì bỏ chunk cũ, giữ mép "đang nói" thay vì dịch lại âm thanh đã trễ
_HELLO_TIMEOUT_SECONDS = 10
_TRANSLATE_PROMPT = (
	"Translate the user's English subtitle line into natural Vietnamese. "
	"Output only the Vietnamese translation, no quotes, no notes. "
	"Use Vietnamese only: never output Chinese or any other language."
)
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
_TRANSLATE_ATTEMPTS = 2


class _Unavailable(Exception):
	def __init__(self, code: str) -> None:
		super().__init__(code)
		self.code = code


async def translate_to_vi(text: str) -> str:
	settings = get_settings()
	client = ollama.AsyncClient(host=settings.ollama_base_url, timeout=30)
	for _ in range(_TRANSLATE_ATTEMPTS):
		reply = await client.chat(
			model=settings.ollama_model_name,
			messages=[{"role": "system", "content": _TRANSLATE_PROMPT}, {"role": "user", "content": text}],
			keep_alive=local_call_service._OLLAMA_KEEP_ALIVE,
			options={"temperature": 0.2, "num_predict": 200},
		)
		translation = reply["message"]["content"].strip()
		# qwen thỉnh thoảng chêm chữ Hán vào câu tiếng Việt: thử lại, vẫn lỗi thì coi như không dịch được.
		if translation and not _CJK.search(translation):
			return translation
	raise ValueError("translation_not_vietnamese")


class LocalEngine:
	name = "local"

	def __init__(self, send) -> None:
		self.send = send
		self.failed: Exception | None = None
		self._vads = {source: local_call_service.EnergyVad(end_silence=0.8) for source in _SOURCE_NAMES}
		self._ids = {source: 0 for source in _SOURCE_NAMES}
		self._stt_lock = asyncio.Lock()  # FIFO: phụ đề ra đúng thứ tự nói
		self._tasks: set[asyncio.Task] = set()

	async def start(self) -> None:
		await run_in_threadpool(local_call_service.ensure_models)

	async def feed(self, source: int, pcm: bytes) -> None:
		for event in self._vads[source].feed(pcm):
			if event[0] == "utterance":
				self._ids[source] += 1
				task = asyncio.create_task(self._caption(source, self._ids[source], event[1]))
				self._tasks.add(task)
				task.add_done_callback(self._tasks.discard)

	async def _caption(self, source: int, caption_id: int, pcm: bytes) -> None:
		base = {"type": "caption", "source": _SOURCE_NAMES[source], "id": caption_id, "final": True}
		async with self._stt_lock:
			text = await run_in_threadpool(local_call_service.transcribe, pcm)
		if not text:
			return
		await self.send({**base, "text": text, "translation": None})
		try:
			translation = await translate_to_vi(text)
		except Exception as error:  # noqa: BLE001 — Ollama tắt/chậm: giữ phụ đề tiếng Anh, bỏ phần dịch
			logger.warning("caption translation failed: %s", error)
			return
		await self.send({**base, "text": text, "translation": translation})

	async def close(self) -> None:
		for task in self._tasks:
			task.cancel()
		await asyncio.gather(*self._tasks, return_exceptions=True)


class _SonioxStream:
	"""1 WebSocket Soniox cho 1 nguồn âm (mic / hệ thống)."""

	def __init__(self, source: int, api_key: str, model: str, send, on_failure) -> None:
		self.source, self.api_key, self.model, self.send, self.on_failure = source, api_key, model, send, on_failure
		self.audio: asyncio.Queue[bytes] = asyncio.Queue(maxsize=_SONIOX_QUEUE_CHUNKS)
		self.caption_id = 1
		self.text = self.translation = ""
		self.task = asyncio.create_task(self._run())

	def put(self, pcm: bytes) -> None:
		if self.audio.full():
			with contextlib.suppress(asyncio.QueueEmpty):
				self.audio.get_nowait()
		self.audio.put_nowait(pcm)

	async def _run(self) -> None:
		try:
			async with websockets.connect(_SONIOX_URL, max_size=None) as socket:
				await socket.send(
					json.dumps(
						{
							"api_key": self.api_key,
							"model": self.model,
							"audio_format": "pcm_s16le",
							"sample_rate": 16000,
							"num_channels": 1,
							"language_hints": ["en"],
							"enable_endpoint_detection": True,
							"translation": {"type": "one_way", "target_language": "vi"},
						}
					)
				)
				sender = asyncio.create_task(self._send_audio(socket))
				try:
					async for raw in socket:
						await self._handle(json.loads(raw))
				finally:
					sender.cancel()
		except asyncio.CancelledError:
			raise
		except Exception as error:  # noqa: BLE001 — mọi lỗi mạng/quota/key đều dẫn tới đường lui local
			self.on_failure(error)

	async def _send_audio(self, socket) -> None:
		while True:
			await socket.send(await self.audio.get())

	async def _handle(self, payload: dict) -> None:
		if payload.get("error_code"):
			raise RuntimeError(f"soniox {payload['error_code']}: {payload.get('error_message')}")
		interim, interim_translation, endpoint = "", "", False
		for token in payload.get("tokens") or []:
			text = token.get("text") or ""
			if text == "<end>":
				endpoint = True
			elif text == "<fin>":
				continue
			elif token.get("translation_status") == "translation":
				if token.get("is_final"):
					self.translation += text
				else:
					interim_translation += text
			elif token.get("is_final"):
				self.text += text
			else:
				interim += text
		shown = (self.text + interim).strip()
		if shown:
			await self.send(
				{
					"type": "caption",
					"source": _SOURCE_NAMES[self.source],
					"id": self.caption_id,
					"text": shown,
					"translation": (self.translation + interim_translation).strip() or None,
					"final": endpoint,
				}
			)
		if endpoint:
			self.caption_id += 1
			self.text = self.translation = ""

	async def close(self) -> None:
		self.task.cancel()
		await asyncio.gather(self.task, return_exceptions=True)


class SonioxEngine:
	name = "soniox"

	def __init__(self, send) -> None:
		settings = get_settings()
		self.send, self.api_key, self.model = send, settings.soniox_api_key, settings.soniox_model
		self.failed: Exception | None = None
		self._streams: dict[int, _SonioxStream] = {}

	async def start(self) -> None:
		pass  # kết nối mở lười ở chunk đầu của từng nguồn

	def _fail(self, error: Exception) -> None:
		self.failed = self.failed or error

	async def feed(self, source: int, pcm: bytes) -> None:
		if source not in self._streams:
			self._streams[source] = _SonioxStream(source, self.api_key, self.model, self.send, self._fail)
		self._streams[source].put(pcm)

	async def close(self) -> None:
		await asyncio.gather(*(stream.close() for stream in self._streams.values()))


def _pick_engine(provider: str):
	has_key = bool(get_settings().soniox_api_key)
	return SonioxEngine if provider == "soniox" or (provider == "auto" and has_key) else LocalEngine


async def _fall_back(failed: SonioxEngine, send) -> LocalEngine:
	logger.warning("soniox failed, falling back to local: %s", failed.failed)
	await failed.close()
	local = LocalEngine(send)
	try:
		await local.start()
	except Exception:  # noqa: BLE001
		raise _Unavailable("local_models_unavailable") from None
	await send({"type": "engine", "name": local.name, "reason": "soniox_failed"})
	return local


async def run_captions(websocket: WebSocket) -> None:
	await websocket.accept()
	try:
		hello = await asyncio.wait_for(websocket.receive_json(), _HELLO_TIMEOUT_SECONDS)
	except WebSocketDisconnect:
		return  # client đã ngắt trước khi gửi hello: đóng lần nữa sẽ ném RuntimeError "Unexpected ASGI message"
	except (asyncio.TimeoutError, ValueError, KeyError):
		await websocket.close(code=1008)
		return
	if not isinstance(hello, dict):
		hello = {}
	async with get_session_factory()() as db:
		auth = await _authenticate(db, hello)
	if auth is None:
		await websocket.send_json({"type": "error", "code": "invalid_token"})
		await websocket.close(code=1008)
		return

	provider = hello.get("provider") if hello.get("provider") in ("soniox", "local") else "auto"
	if provider == "soniox" and not get_settings().soniox_api_key:
		await websocket.send_json({"type": "error", "code": "captions_not_configured"})
		await websocket.close()
		return

	async def send(message: dict) -> None:
		with contextlib.suppress(Exception):  # trình duyệt đã đóng giữa chừng
			await websocket.send_json(message)

	engine = _pick_engine(provider)(send)
	gate = EchoGate()
	error_code = None
	try:
		try:
			await engine.start()
		except Exception:  # noqa: BLE001 — tải model local lỗi (mất mạng lần đầu...)
			raise _Unavailable("local_models_unavailable") from None
		await websocket.send_json({"type": "ready", "engine": engine.name, "max_seconds": MAX_CALL_SECONDS})
		loop = asyncio.get_running_loop()
		deadline = loop.time() + MAX_CALL_SECONDS
		while (remaining := deadline - loop.time()) > 0:
			try:
				message = await asyncio.wait_for(websocket.receive(), remaining)
			except asyncio.TimeoutError:
				break
			if message["type"] == "websocket.disconnect":
				break
			data = message.get("bytes")
			if data is None:
				with contextlib.suppress(ValueError, TypeError, AttributeError):
					if json.loads(message.get("text") or "").get("type") == "end":
						break
				continue
			if len(data) < 2 or len(data) > MAX_AUDIO_FRAME_BYTES or data[0] not in _SOURCE_NAMES:
				continue
			source, pcm = data[0], data[1:]
			if source == SYSTEM:
				gate.push_system(pcm)
			else:
				pcm = gate.filter_mic(pcm)
			if engine.failed is not None:
				engine = await _fall_back(engine, send)
			await engine.feed(source, pcm)
	except WebSocketDisconnect:
		pass
	except _Unavailable as error:
		error_code = error.code
	except Exception as error:  # noqa: BLE001 — báo về client, không làm sập socket
		logger.warning("captions failed: %s", error)
		error_code = "captions_unavailable"
	finally:
		await engine.close()
	with contextlib.suppress(Exception):
		if error_code:
			await websocket.send_json({"type": "error", "code": error_code})
		await websocket.send_json({"type": "ended"})
		await websocket.close()
