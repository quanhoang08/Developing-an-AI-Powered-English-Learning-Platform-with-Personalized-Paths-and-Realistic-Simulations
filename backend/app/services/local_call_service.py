# Gọi thoại chạy hoàn toàn local (F22, nhánh Ollama): Ollama chỉ nhận/trả chữ nên ghép chuỗi
#   mic -> VAD (tự biết người học nói xong) -> faster-whisper -> Ollama (stream) -> Piper (đọc từng câu) -> loa.
# STT và TTS chạy CPU để không tranh VRAM với Ollama. Dùng chung giao thức WebSocket với live_call_service
# (xem đầu file đó), khác là server tự làm hết phần Gemini Live làm hộ: cắt lượt, ngắt lời, ghép câu.
import asyncio
import contextlib
import json
import logging
import re
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np
import ollama
from fastapi import WebSocket
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.models.speaking import Scenario
from app.models.user import User
from app.services import llm_service
from app.services.live_call_service import (
	MAX_AUDIO_FRAME_BYTES,
	MAX_CALL_SECONDS,
	append_transcript,
	build_system_prompt,
)

logger = logging.getLogger(__name__)

INPUT_RATE = 16000
OUTPUT_RATE = 24000  # trình duyệt phát 24kHz (cùng nhánh Gemini); Piper ra 22.05kHz nên resample.
_MAX_HISTORY_MESSAGES = 20
_GREETING = "(The call has connected. Greet the learner in character, in one or two short sentences.)"
_LOCAL_STYLE = (
	"This is a spoken call: reply in plain spoken English, at most two short sentences, "
	"no lists, no markdown, no emojis."
)
_WARMUP_TIMEOUT_SECONDS = 90
_OLLAMA_KEEP_ALIVE = "30m"


class EnergyVad:
	"""VAD theo năng lượng, đủ để cắt lượt nói của 1 người ở chỗ yên tĩnh.

	feed() nhận từng frame PCM16 16kHz mono (frame mic ~128ms), trả danh sách sự kiện:
	("start",) khi bắt đầu nói; ("utterance", pcm) khi nói xong (im lặng >= end_silence); ("discard",) nếu
	quá ngắn (ho, click). `strict` nâng ngưỡng khi AI đang nói để tiếng vọng của chính AI không tính là ngắt lời.
	# ponytail: ngưỡng RMS thích nghi theo nền ồn, sẽ nhầm ở chỗ ồn/nhiều người nói; nâng lên Silero VAD nếu cần.
	"""

	def __init__(self, end_silence: float = 0.7, min_speech: float = 0.3, max_utterance: float = 30.0) -> None:
		self.end_silence, self.min_speech, self.max_utterance = end_silence, min_speech, max_utterance
		self.noise = 150.0
		self._preroll: deque[bytes] = deque(maxlen=2)  # giữ ~256ms trước lúc phát hiện để không mất âm đầu
		self._reset()

	def _reset(self) -> None:
		self.active = False
		self._buf = bytearray()
		self._speech = self._silence = 0.0
		self._loud_run = 0

	def feed(self, pcm: bytes, strict: bool = False) -> list[tuple]:
		pcm = pcm[: len(pcm) // 2 * 2]
		if not pcm:
			return []
		duration = len(pcm) / (INPUT_RATE * 2)
		rms = float(np.sqrt(np.mean(np.frombuffer(pcm, dtype=np.int16).astype(np.float32) ** 2)))
		loud = rms > max(400.0, self.noise * 3) * (2.0 if strict else 1.0)
		if not self.active:
			self._preroll.append(pcm)
			if not loud:
				self.noise = 0.95 * self.noise + 0.05 * rms  # chỉ học nền ồn lúc yên tĩnh
				self._loud_run = 0
				return []
			self._loud_run += 1
			if self._loud_run < (3 if strict else 2):
				return []
			self.active = True
			self._buf = bytearray(b"".join(self._preroll))
			self._speech, self._silence = self._loud_run * duration, 0.0
			return [("start",)]
		self._buf += pcm
		if loud:
			self._speech, self._silence = self._speech + duration, 0.0
		else:
			self._silence += duration
		if self._silence >= self.end_silence or len(self._buf) / (INPUT_RATE * 2) >= self.max_utterance:
			event = ("utterance", bytes(self._buf)) if self._speech >= self.min_speech else ("discard",)
			self._reset()
			return [event]
		return []


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def split_sentences(buffer: str) -> tuple[list[str], str]:
	"""Tách các câu đã hoàn chỉnh khỏi phần đang sinh dở (để TTS đọc từng câu ngay khi LLM viết xong câu đó)."""
	parts = _SENTENCE_END.split(buffer)
	return [p.strip() for p in parts[:-1] if p.strip()], parts[-1]


def clean_for_speech(text: str) -> str:
	return re.sub(r"[*_#`~>]+", "", text).strip()


def resample_pcm16(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
	if src_rate == dst_rate or not pcm:
		return pcm
	samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
	positions = np.arange(int(len(samples) * dst_rate / src_rate)) * (src_rate / dst_rate)
	return np.interp(positions, np.arange(len(samples)), samples).astype(np.int16).tobytes()


def trim_history(history: list[dict]) -> list[dict]:
	"""Giữ system prompt + các tin gần nhất để prompt không phình theo độ dài cuộc gọi."""
	return history[:1] + history[1:][-_MAX_HISTORY_MESSAGES:]


# --- Model STT/TTS: nạp lười, dùng chung cho mọi cuộc gọi ---
_models_lock = threading.Lock()
_whisper = None
_piper = None
_warmed = False


def ensure_models() -> None:
	"""Nạp (lần đầu: tải) faster-whisper và giọng Piper. Chạy trong threadpool — lần tải đầu mất vài phút."""
	global _whisper, _piper, _warmed
	settings = get_settings()
	root = Path(settings.local_models_dir)
	with _models_lock:
		if _whisper is None:
			from faster_whisper import WhisperModel

			_whisper = WhisperModel(
				settings.whisper_model_name, device="cpu", compute_type="int8", download_root=str(root / "whisper")
			)
		if _piper is None:
			from piper import PiperVoice
			from piper.download_voices import download_voice

			voice_dir = root / "piper"
			voice_dir.mkdir(parents=True, exist_ok=True)
			if not (voice_dir / f"{settings.piper_voice}.onnx").exists():
				download_voice(settings.piper_voice, voice_dir)
			_piper = PiperVoice.load(str(voice_dir / f"{settings.piper_voice}.onnx"))
		if not _warmed:
			# Lần suy luận đầu của CTranslate2/ONNX chậm gấp ~2.5 lần (đo: STT 6s audio mất 3.6s lần đầu, 1.4s sau đó),
			# nên chạy thử 1 lượt ở đây — trước lúc báo "ready" — thay vì để người học chịu ở câu nói đầu tiên.
			noise = np.random.default_rng(0).normal(0, 0.01, INPUT_RATE * 2).astype(np.float32)
			list(_whisper.transcribe(noise, language="en", beam_size=1)[0])
			synthesize("Hello.")
			_warmed = True


def transcribe(pcm: bytes) -> str:
	audio = np.frombuffer(pcm[: len(pcm) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768
	# vad_filter loại đoạn không phải tiếng nói để Whisper không "bịa" chữ ("Thank you.") từ tiếng ồn.
	segments, _ = _whisper.transcribe(
		audio, language="en", beam_size=1, vad_filter=True, condition_on_previous_text=False
	)
	return " ".join(segment.text.strip() for segment in segments).strip()


def synthesize(text: str) -> bytes:
	return b"".join(
		resample_pcm16(chunk.audio_int16_bytes, chunk.sample_rate, OUTPUT_RATE) for chunk in _piper.synthesize(text)
	)


async def _warm_ollama() -> None:
	"""Nạp model lên GPU trước khi báo "ready": lần nạp đầu mất 5-15s, không nên rơi vào lời chào của AI."""
	settings = get_settings()
	client = ollama.AsyncClient(host=settings.ollama_base_url, timeout=_WARMUP_TIMEOUT_SECONDS)
	try:
		await client.generate(model=settings.ollama_model_name, prompt="", keep_alive=_OLLAMA_KEEP_ALIVE)
	except Exception as error:  # noqa: BLE001 — phân loại (tắt/thiếu model/quá chậm) nằm trong _ollama_error
		raise llm_service._ollama_error(error) from error


async def _stream_ollama(history: list[dict]):
	settings = get_settings()
	client = ollama.AsyncClient(host=settings.ollama_base_url, timeout=60)
	stream = await client.chat(
		model=settings.ollama_model_name,
		messages=history,
		stream=True,
		keep_alive=_OLLAMA_KEEP_ALIVE,
		options={"temperature": settings.ollama_temperature, "num_predict": 150},
	)
	async for part in stream:
		yield part["message"]["content"]


async def converse(
	websocket: WebSocket,
	user: User,
	scenario: Scenario | None,
	transcript: list[dict],
	prior: list[dict] | None = None,
) -> str | None:
	"""Chạy 1 cuộc gọi local tới khi cúp máy/hết giờ. Trả mã lỗi (hoặc None nếu kết thúc bình thường).

	prior: transcript cuộc gọi Gemini vừa đứt (hết quota) — đưa vào system prompt để nói tiếp thay vì chào lại.
	"""
	try:
		await run_in_threadpool(ensure_models)
		await _warm_ollama()
	except llm_service.AIServiceError as error:
		return error.code
	except Exception:  # noqa: BLE001 — tải model STT/TTS lỗi (mất mạng lần đầu...)
		return "local_models_unavailable"
	await websocket.send_json({"type": "ready", "max_seconds": MAX_CALL_SECONDS})

	system = build_system_prompt(user.target_level, scenario) + "\n" + _LOCAL_STYLE
	opener = _GREETING
	if prior:
		recap = "\n".join(f"{'Learner' if line['role'] == 'user' else 'You'}: {line['text']}" for line in prior)
		system += f"\nThis call was cut off and reconnected. Conversation so far:\n{recap}"
		opener = "(The call reconnected. Say a very short 'sorry, we got cut off' and continue naturally from where you left off.)"
	history: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": opener}]
	vad = EnergyVad()
	stt_lock = asyncio.Lock()  # FIFO: các câu được nhận dạng và đưa vào hội thoại đúng thứ tự nói
	playing_until = 0.0  # thời điểm (monotonic) giọng AI đã gửi sẽ phát xong ở trình duyệt
	reply_task: asyncio.Task | None = None
	background: set[asyncio.Task] = set()
	reply_started = [0.0]  # perf_counter lúc lượt trả lời hiện tại bắt đầu, chỉ để ghi log độ trễ

	def ai_audible() -> bool:
		return (reply_task is not None and not reply_task.done()) or time.monotonic() < playing_until

	async def say(sentence: str, spoken: list[str]) -> None:
		nonlocal playing_until
		text = clean_for_speech(sentence)
		if not text:
			return
		audio = await run_in_threadpool(synthesize, text)
		await websocket.send_bytes(audio)
		if not spoken:
			logger.info("local call first audio %.2fs after reply start", time.perf_counter() - reply_started[0])
		playing_until = max(playing_until, time.monotonic()) + len(audio) / (OUTPUT_RATE * 2)
		spoken.append(sentence)
		append_transcript(transcript, "ai", sentence + " ")
		await websocket.send_json({"type": "transcript", "role": "ai", "text": sentence + " "})

	async def reply() -> None:
		spoken: list[str] = []
		pending = ""
		reply_started[0] = time.perf_counter()
		try:
			async for piece in _stream_ollama(trim_history(history)):
				pending += piece
				sentences, pending = split_sentences(pending)
				for sentence in sentences:
					await say(sentence, spoken)
			if pending.strip():
				await say(pending.strip(), spoken)
			await websocket.send_json({"type": "turn_complete"})
		except asyncio.CancelledError:
			raise  # bị ngắt lời: phần đã nói vẫn được lưu vào hội thoại ở khối finally
		except Exception as error:  # noqa: BLE001 — Ollama lỗi giữa cuộc gọi: báo nhưng giữ cuộc gọi sống
			code = llm_service._ollama_error(error).code if not hasattr(error, "code") else error.code
			with contextlib.suppress(Exception):
				await websocket.send_json({"type": "error", "code": code})
		finally:
			if spoken:
				history.append({"role": "assistant", "content": " ".join(spoken)})

	async def stop_reply() -> None:
		# Phải đợi lượt cũ dọn xong để phần AI đã nói dở nằm TRƯỚC câu mới của người học trong lịch sử.
		if reply_task is not None and not reply_task.done():
			reply_task.cancel()
			await asyncio.gather(reply_task, return_exceptions=True)

	async def handle_utterance(pcm: bytes) -> None:
		nonlocal reply_task
		async with stt_lock:
			started = time.perf_counter()
			text = await run_in_threadpool(transcribe, pcm)
			logger.info("local call stt=%.2fs audio=%.1fs", time.perf_counter() - started, len(pcm) / (INPUT_RATE * 2))
			if not text:
				return
			append_transcript(transcript, "user", text + " ")
			await websocket.send_json({"type": "transcript", "role": "user", "text": text + " "})
			await stop_reply()
			# Người học ngắt AI rồi nói tiếp khi lượt trước chưa được trả lời: gộp vào cùng 1 tin nhắn user.
			if history[-1]["role"] == "user":
				history[-1]["content"] += " " + text
			else:
				history.append({"role": "user", "content": text})
			reply_task = asyncio.create_task(reply())

	reply_task = asyncio.create_task(reply())  # AI chào trước
	deadline = time.monotonic() + MAX_CALL_SECONDS
	try:
		while (remaining := deadline - time.monotonic()) > 0:
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
			if len(data) > MAX_AUDIO_FRAME_BYTES:
				continue
			for event in vad.feed(data, strict=ai_audible()):
				if event[0] == "start" and ai_audible():
					# Người học nói chen: dừng sinh/đọc tiếp và bảo trình duyệt bỏ phần giọng AI đang chờ phát.
					if reply_task is not None and not reply_task.done():
						reply_task.cancel()
					playing_until = 0.0
					await websocket.send_json({"type": "interrupted"})
				elif event[0] == "utterance":
					task = asyncio.create_task(handle_utterance(event[1]))
					background.add(task)
					task.add_done_callback(background.discard)
	finally:
		tasks = [*background, *([reply_task] if reply_task else [])]
		for task in tasks:
			task.cancel()
		await asyncio.gather(*tasks, return_exceptions=True)
	return None
