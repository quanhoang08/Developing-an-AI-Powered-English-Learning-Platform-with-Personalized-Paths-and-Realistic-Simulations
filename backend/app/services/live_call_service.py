# Gọi thoại 2 chiều liên tục (F22): backend làm cầu nối WebSocket trình duyệt <-> Gemini Live.
# Audio đi theo luồng cả 2 chiều, Gemini tự phát hiện người học nói xong (VAD) và cho ngắt lời
# (barge-in), nên không còn mô hình luân phiên STT -> LLM -> TTS như speaking_service. API key ở lại
# server. provider="ollama" chạy nhánh local (local_call_service) — cùng giao thức, tự ghép STT/LLM/TTS.
#
# Giao thức với trình duyệt:
#   client -> server: tin đầu là JSON {"token", "scenario_id"?, "provider"?: "gemini"|"ollama"}; sau đó frame nhị phân PCM16 16kHz
#                     mono; JSON {"type": "end"} để cúp máy.
#   server -> client: frame nhị phân PCM16 24kHz mono (giọng AI); JSON {"type": "ready" |
#                     "transcript" (role, text) | "interrupted" | "turn_complete" | "ended" (call_id) |
#                     "error" (code)}.
import asyncio
import contextlib
import json
import logging
import time
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.database import get_session_factory
from app.models.speaking import LiveCall, Scenario
from app.models.user import User
from app.services.gamification_service import award_activity
from app.services.llm_service import persona_style

logger = logging.getLogger(__name__)

# Chặn cuộc gọi treo đốt quota free tier; Gemini tự cắt phiên audio ở ~15 phút.
MAX_CALL_SECONDS = 600
_HELLO_TIMEOUT_SECONDS = 10
# 1 frame mic thường ~100ms (3.2KB); frame lớn bất thường là client lỗi/độc hại -> bỏ.
MAX_AUDIO_FRAME_BYTES = 64 * 1024
_INPUT_MIME = "audio/pcm;rate=16000"


def append_transcript(transcript: list[dict], role: str, text: str) -> None:
	"""Gemini gửi transcript theo từng mẩu: nối vào câu cuối nếu cùng người nói, không thì mở câu mới."""
	if not text:
		return
	if transcript and transcript[-1]["role"] == role:
		transcript[-1]["text"] += text
	else:
		transcript.append({"role": role, "text": text})


def _clean(transcript: list[dict]) -> list[dict]:
	return [{"role": item["role"], "text": item["text"].strip()} for item in transcript if item["text"].strip()]


def _prior(hello: dict) -> list[dict]:
	"""Transcript client gửi để nói tiếp sau khi Gemini hết quota. Chỉ ảnh hưởng prompt của chính user nên chỉ cần cắt cỡ."""
	raw = hello.get("prior_transcript")
	if not isinstance(raw, list):
		return []
	return [
		{"role": "user" if item.get("role") == "user" else "ai", "text": item["text"].strip()[:500]}
		for item in raw[-30:]
		if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip()
	]


def build_system_prompt(target_level: str | None, scenario: Scenario | None, persona: str | None = None) -> str:
	level = target_level or "B1"
	lines = [
		"You are Lumina, a warm English speaking tutor on a live voice call with a Vietnamese learner"
		f" at CEFR level {level}.",
		"Speak naturally like a real phone call: short turns of 1-3 sentences, then let the learner talk.",
		f"Use vocabulary and grammar suitable for {level}; ask follow-up questions to keep them speaking.",
		"If the learner makes a clear mistake, briefly say the correct version once, then move on.",
		"Speak English only. If the learner is clearly stuck, you may give one short hint in Vietnamese.",
	]
	if scenario is not None:
		lines.append(f"Role-play this scene: {scenario.title}. {scenario.description or ''}".strip())
		if scenario.goal:
			lines.append(f"The learner's goal in this scene: {scenario.goal}")
		lines.append(f"Keep the register {scenario.formality_level}. Open the call in character.")
	else:
		lines.append("This is free conversation: greet the learner and ask what they'd like to talk about.")
	if style := persona_style(persona):
		lines.append(f"{style} Keep teaching correctly in this personality.")
	return "\n".join(lines)


def _error_code(error: Exception) -> str:
	text = str(error)
	if "RESOURCE_EXHAUSTED" in text or "429" in text or "quota" in text.lower():
		return "ai_quota_exceeded"
	return "live_unavailable"


async def _authenticate(db: AsyncSession, hello: dict) -> tuple[User, Scenario | None] | None:
	user_id = decode_access_token(str(hello.get("token") or ""))
	if user_id is None:
		return None
	user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
	if user is None:
		return None
	scenario = None
	if hello.get("scenario_id"):
		with contextlib.suppress(ValueError):
			scenario = await db.get(Scenario, uuid.UUID(str(hello["scenario_id"])))
	return user, scenario


async def _pump_browser(websocket: WebSocket, session) -> None:
	# Mic trình duyệt -> Gemini. Kết thúc khi người học cúp máy hoặc mất kết nối.
	while True:
		message = await websocket.receive()
		if message["type"] == "websocket.disconnect":
			return
		data = message.get("bytes")
		if data:
			if len(data) <= MAX_AUDIO_FRAME_BYTES:
				await session.send_realtime_input(audio=types.Blob(data=data, mime_type=_INPUT_MIME))
			continue
		with contextlib.suppress(ValueError, TypeError, AttributeError):
			if json.loads(message.get("text") or "").get("type") == "end":
				return


async def _pump_gemini(session, websocket: WebSocket, transcript: list[dict]) -> None:
	# Gemini -> trình duyệt. session.receive() dừng sau mỗi turn_complete nên phải lặp lại.
	while True:
		async for message in session.receive():
			content = message.server_content
			if content is None:
				continue
			# Đọc thẳng inline_data thay vì message.data (thuộc tính đó log cảnh báo mỗi khi model kèm "thought").
			for part in (content.model_turn.parts or []) if content.model_turn else []:
				if part.inline_data and part.inline_data.data:
					await websocket.send_bytes(part.inline_data.data)
			for role, chunk in (("user", content.input_transcription), ("ai", content.output_transcription)):
				if chunk and chunk.text:
					append_transcript(transcript, role, chunk.text)
					await websocket.send_json({"type": "transcript", "role": role, "text": chunk.text})
			if content.interrupted:
				await websocket.send_json({"type": "interrupted"})
			if content.turn_complete:
				await websocket.send_json({"type": "turn_complete"})


async def _save(user: User, scenario: Scenario | None, transcript: list[dict], seconds: int) -> uuid.UUID | None:
	lines = _clean(transcript)
	# Người học chưa nói câu nào thì không tính là đã luyện: không lưu, không cộng XP.
	if not any(item["role"] == "user" for item in lines):
		return None
	async with get_session_factory()() as db:
		call = LiveCall(
			user_id=user.id,
			scenario_id=scenario.id if scenario else None,
			duration_seconds=seconds,
			transcript=lines,
		)
		db.add(call)
		# Thời gian học chỉ ghi khi user bật chế độ bấm giờ — cùng quy ước với award_activity.
		await award_activity(
			db, user.id, "live_call", duration_seconds=seconds if user.timer_mode_enabled else None
		)
		await db.commit()
		return call.id


async def _converse_gemini(
	websocket: WebSocket, user: User, scenario: Scenario | None, transcript: list[dict], persona: str | None = None
) -> None:
	settings = get_settings()
	config = types.LiveConnectConfig(
		response_modalities=[types.Modality.AUDIO],
		system_instruction=build_system_prompt(user.target_level, scenario, persona),
		input_audio_transcription=types.AudioTranscriptionConfig(),
		output_audio_transcription=types.AudioTranscriptionConfig(),
	)
	client = genai.Client(api_key=settings.google_api_key)
	async with client.aio.live.connect(model=settings.gemini_live_model, config=config) as session:
		await websocket.send_json({"type": "ready", "max_seconds": MAX_CALL_SECONDS})
		if scenario is not None:
			# Nhân vật mở lời trước để người học biết bối cảnh.
			await session.send_realtime_input(text="(The call has connected. Greet the learner in character.)")
		tasks = {
			asyncio.create_task(_pump_browser(websocket, session)),
			asyncio.create_task(_pump_gemini(session, websocket, transcript)),
		}
		done, pending = await asyncio.wait(tasks, timeout=MAX_CALL_SECONDS, return_when=asyncio.FIRST_COMPLETED)
		for task in pending:
			task.cancel()
		await asyncio.gather(*pending, return_exceptions=True)
		for task in done:
			failure = task.exception()
			# Trình duyệt tự đóng là chuyện bình thường; lỗi phía Gemini (hết quota giữa chừng...) thì báo.
			if failure is not None and not isinstance(failure, WebSocketDisconnect):
				raise failure


async def run_call(websocket: WebSocket) -> None:
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
	# Session DB ngắn, KHÔNG giữ suốt cuộc gọi (cuộc gọi kéo dài vài phút sẽ chiếm connection pool).
	async with get_session_factory()() as db:
		auth = await _authenticate(db, hello)
	if auth is None:
		await websocket.send_json({"type": "error", "code": "invalid_token"})
		await websocket.close(code=1008)
		return
	user, scenario = auth
	persona = hello.get("persona") if isinstance(hello.get("persona"), str) else None

	transcript: list[dict] = []
	started = time.monotonic()
	error_code = None
	try:
		if hello.get("provider") == "ollama":
			# Import lười: local_call_service import lại các hàm dùng chung của file này.
			from app.services import local_call_service

			error_code = await local_call_service.converse(
				websocket, user, scenario, transcript, _prior(hello), persona
			)
		else:
			await _converse_gemini(websocket, user, scenario, transcript, persona)
	except WebSocketDisconnect:
		pass
	except Exception as error:  # noqa: BLE001 — mọi lỗi Gemini/mạng đều phải báo về client, không làm sập socket
		logger.warning("live call failed: %s", error)
		error_code = _error_code(error)

	seconds = max(1, round(time.monotonic() - started))
	call_id = None
	try:
		call_id = await _save(user, scenario, transcript, seconds)
	except Exception:  # noqa: BLE001
		logger.exception("could not save live call")
	with contextlib.suppress(Exception):
		if error_code:
			await websocket.send_json({"type": "error", "code": error_code})
		await websocket.send_json({"type": "ended", "call_id": str(call_id) if call_id else None})
		await websocket.close()


async def list_calls(db: AsyncSession, user_id: uuid.UUID, limit: int = 20) -> list[tuple[LiveCall, str | None]]:
	rows = await db.execute(
		select(LiveCall, Scenario.title)
		.outerjoin(Scenario, Scenario.id == LiveCall.scenario_id)
		.where(LiveCall.user_id == user_id)
		.order_by(LiveCall.created_at.desc())
		.limit(limit)
	)
	return [(call, title) for call, title in rows.all()]
