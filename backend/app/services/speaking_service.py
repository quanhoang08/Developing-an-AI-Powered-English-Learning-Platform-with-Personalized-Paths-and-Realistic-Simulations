# Business logic Speaking turn-based (feature-speaking.md mục 1): STT + LLM (nhánh A) chạy song
# song với Pronunciation Assessment (nhánh B), gộp thành 1 dòng conversation_turns.
import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.models.listening import Persona
from app.models.speaking import (
	ConversationSession,
	ConversationTurn,
	PhrasebookEntry,
	Scenario,
	SlangPhrase,
)
from app.services import llm_service, speech_service
from app.services.gamification_service import award_activity

logger = logging.getLogger(__name__)

SESSION_IDLE_MINUTES = 30
_ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm", ".ogg"}
_MAX_ADVICE_WORDS = 5


def _audio_dir() -> Path:
	settings = get_settings()
	root = Path(__file__).resolve().parents[2] / settings.storage_audio_dir
	root.mkdir(parents=True, exist_ok=True)
	return root


def _clamp_score(value) -> float | None:
	# LLM trả thiếu/sai kiểu -> NULL thay vì áng chừng (mục 3.3).
	try:
		return float(min(100, max(0, int(value))))
	except (TypeError, ValueError):
		return None


async def list_scenarios(db: AsyncSession, formality_level: str | None) -> list[Scenario]:
	query = select(Scenario).order_by(Scenario.title.asc())
	if formality_level:
		query = query.where(Scenario.formality_level == formality_level)
	return list((await db.execute(query)).scalars().all())


async def create_session(
	db: AsyncSession, user_id: uuid.UUID, scenario_id: uuid.UUID, persona_id: uuid.UUID | None
) -> ConversationSession:
	scenario = await db.get(Scenario, scenario_id)
	if scenario is None:
		raise ValueError("scenario_not_found")
	session = ConversationSession(user_id=user_id, scenario_id=scenario_id, persona_id=persona_id)
	db.add(session)
	await db.commit()
	await db.refresh(session)
	return session


async def get_owned_session(
	db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID
) -> ConversationSession:
	session = await db.scalar(
		select(ConversationSession).where(
			ConversationSession.id == session_id, ConversationSession.user_id == user_id
		)
	)
	if session is None:
		raise ValueError("session_not_found")
	return session


async def list_turns(db: AsyncSession, session_id: uuid.UUID) -> list[ConversationTurn]:
	result = await db.execute(
		select(ConversationTurn)
		.where(ConversationTurn.conversation_session_id == session_id)
		.order_by(ConversationTurn.turn_index.asc())
	)
	return list(result.scalars().all())


def _build_pronunciation_advice(result: speech_service.PronunciationResult) -> str:
	if not result.weak_words:
		return "Your pronunciation was clear. Keep it up!"
	words = ", ".join(result.weak_words[:_MAX_ADVICE_WORDS])
	return f"Practise these words again: {words}."


async def _assess_pronunciation(audio_path: str) -> speech_service.PronunciationResult | None:
	# Nhánh B: lỗi/timeout -> None + cờ lỗi, KHÔNG chặn lượt hội thoại (mục 1.4).
	try:
		return await run_in_threadpool(speech_service.assess_pronunciation, audio_path)
	except speech_service.SpeechServiceError as error:
		logger.warning("pronunciation assessment failed: %s", error)
		return None


async def _transcribe_and_reply(
	audio_path: str, scenario: Scenario, history: list[dict], provider: str | None
) -> tuple[str, str, dict]:
	# Nhánh A: STT (Azure -> Gemini dự phòng) -> LLM. Cả 2 STT lỗi -> stt_service_unavailable,
	# rỗng -> empty_transcription.
	try:
		raw_text, stt_provider = await run_in_threadpool(
			speech_service.transcribe_with_fallback, audio_path
		)
	except speech_service.SpeechServiceError as error:
		raise ValueError("stt_service_unavailable") from error
	text = raw_text.strip()
	if not text:
		raise ValueError("empty_transcription")
	scenario_payload = {
		"description": scenario.description,
		"goal": scenario.goal,
		"formality_level": scenario.formality_level,
	}
	reply = await llm_service.generate_conversation_turn(scenario_payload, history, text, provider)
	return text, stt_provider, reply


async def _synthesize_reply(text: str, persona_id: uuid.UUID | None, db: AsyncSession) -> str | None:
	# TTS phản hồi: lỗi không chặn lượt (audio là phần bổ trợ, text vẫn trả cho client).
	voice = None
	if persona_id is not None:
		persona = await db.get(Persona, persona_id)
		if persona is not None and persona.is_active and persona.provider == "azure":
			voice = persona.voice_id
	try:
		audio = await run_in_threadpool(speech_service.synthesize_azure_speech, text, voice)
	except speech_service.SpeechServiceError as error:
		logger.warning("reply TTS failed: %s", error)
		return None
	dest = _audio_dir() / f"reply_{uuid.uuid4()}.wav"
	dest.write_bytes(audio)
	return str(dest)


async def submit_turn(
	db: AsyncSession,
	user_id: uuid.UUID,
	session_id: uuid.UUID,
	audio: UploadFile,
	provider: str | None = None,
	duration_seconds: int | None = None,
) -> ConversationTurn:
	started = time.perf_counter()
	session = await get_owned_session(db, user_id, session_id)
	if session.status != "in_progress":
		raise ValueError("session_not_active")

	turns = await list_turns(db, session.id)
	last_activity = turns[-1].created_at if turns else session.started_at
	now = datetime.now(timezone.utc)
	if last_activity is not None:
		if last_activity.tzinfo is None:
			last_activity = last_activity.replace(tzinfo=timezone.utc)
		if now - last_activity > timedelta(minutes=SESSION_IDLE_MINUTES):
			session.status = "expired"
			await db.commit()
			raise ValueError("session_expired")

	extension = Path(audio.filename or "").suffix.lower()
	if extension not in _ALLOWED_AUDIO_EXTENSIONS:
		raise ValueError("unsupported_audio_type")
	content = await audio.read()
	if not content:
		raise ValueError("empty_audio")
	audio_path = _audio_dir() / f"turn_{uuid.uuid4()}{extension}"
	audio_path.write_bytes(content)

	scenario = await db.get(Scenario, session.scenario_id)
	history: list[dict] = []
	for turn in turns:
		history.append({"role": "learner", "content": turn.user_transcript or ""})
		history.append({"role": "partner", "content": turn.ai_response_text or ""})

	# Hai nhánh độc lập dữ liệu vào: B luôn nhận audio gốc, không nhận text đã qua STT.
	(transcript_text, stt_provider, reply), pronunciation = await asyncio.gather(
		_transcribe_and_reply(str(audio_path), scenario, history, provider),
		_assess_pronunciation(str(audio_path)),
	)

	response_text = reply["response_text"].strip()
	response_audio = await _synthesize_reply(response_text, session.persona_id, db)

	turn = ConversationTurn(
		conversation_session_id=session.id,
		turn_index=len(turns),
		user_audio_url=str(audio_path),
		user_transcript=transcript_text,
		pronunciation_score=pronunciation.score if pronunciation else None,
		pronunciation_advice=_build_pronunciation_advice(pronunciation) if pronunciation else None,
		pronunciation_assessment_failed=pronunciation is None,
		intent_score=_clamp_score(reply.get("intent_score")),
		politeness_score=_clamp_score(reply.get("politeness_score")),
		intent_feedback=reply.get("intent_feedback"),
		politeness_feedback=reply.get("politeness_feedback"),
		suggested_phrases=reply.get("suggested_phrases") or [],
		ai_response_text=response_text,
		ai_response_audio_url=response_audio,
		stt_provider_used=stt_provider,
	)
	db.add(turn)
	# Chỉ lượt hợp lệ (đã qua STT + phản hồi AI) mới tới đây, lượt lỗi đã raise ở trên.
	await award_activity(
		db, user_id, "speaking_turn",
		score=float(pronunciation.score) if pronunciation else None,
		duration_seconds=duration_seconds,
	)
	await db.commit()
	await db.refresh(turn)
	# Đo độ trễ tổng (ghi âm xong -> có phản hồi) phục vụ tiêu chí mục 1.6.
	logger.info(
		"speaking turn latency=%.2fs stt_provider=%s", time.perf_counter() - started, stt_provider
	)
	return turn


async def get_turn_reply_audio_path(
	db: AsyncSession, user_id: uuid.UUID, turn_id: uuid.UUID
) -> str:
	# Ownership qua session.user_id; không phải chủ/không có audio -> cùng lỗi turn_audio_not_found.
	turn = await db.scalar(
		select(ConversationTurn)
		.join(ConversationSession, ConversationSession.id == ConversationTurn.conversation_session_id)
		.where(ConversationTurn.id == turn_id, ConversationSession.user_id == user_id)
	)
	if turn is None or not turn.ai_response_audio_url or not Path(turn.ai_response_audio_url).exists():
		raise ValueError("turn_audio_not_found")
	return turn.ai_response_audio_url


# ---------------------------------------------------------------- Phrasebook (mục 2)


async def list_slang(
	db: AsyncSession, formality_level: str | None, topic: str | None
) -> list[SlangPhrase]:
	query = select(SlangPhrase).order_by(SlangPhrase.phrase_text.asc())
	if formality_level:
		query = query.where(SlangPhrase.formality_level == formality_level)
	if topic:
		query = query.where(SlangPhrase.topic_tags.any(topic))
	return list((await db.execute(query)).scalars().all())


async def save_phrase(
	db: AsyncSession,
	user_id: uuid.UUID,
	slang_phrase_id: uuid.UUID | None,
	conversation_turn_id: uuid.UUID | None,
	phrase_text: str | None,
	meaning: str | None,
	example_sentence: str | None,
) -> tuple[PhrasebookEntry, SlangPhrase | None]:
	"""Lưu 1 cụm vào sổ tay: từ thư viện (snapshot từ slang_phrases) hoặc snapshot do client gửi.
	Lưu lại cùng cụm 2 lần trả bản ghi cũ, không tạo trùng."""
	phrase_text = (phrase_text or "").strip()
	if slang_phrase_id is None and not phrase_text:
		raise ValueError("phrase_data_missing")

	library: SlangPhrase | None = None
	formality: str | None = None
	if slang_phrase_id is not None:
		library = await db.get(SlangPhrase, slang_phrase_id)
		if library is None:
			raise ValueError("slang_phrase_not_found")
		phrase_text, meaning, example_sentence = (
			library.phrase_text, library.meaning, library.example_sentence,
		)
		formality = library.formality_level

	if conversation_turn_id is not None:
		owned_turn = await db.scalar(
			select(ConversationTurn.id)
			.join(ConversationSession, ConversationSession.id == ConversationTurn.conversation_session_id)
			.where(ConversationTurn.id == conversation_turn_id, ConversationSession.user_id == user_id)
		)
		if owned_turn is None:
			raise ValueError("turn_not_found")

	duplicate_filter = (
		PhrasebookEntry.slang_phrase_id == slang_phrase_id
		if slang_phrase_id is not None
		else func.lower(PhrasebookEntry.phrase_text) == phrase_text.lower()
	)
	existing = await db.scalar(
		select(PhrasebookEntry).where(PhrasebookEntry.user_id == user_id, duplicate_filter)
	)
	if existing is not None:
		return existing, library

	entry = PhrasebookEntry(
		user_id=user_id,
		slang_phrase_id=slang_phrase_id,
		conversation_turn_id=conversation_turn_id,
		phrase_text=phrase_text[:150],
		meaning=meaning,
		example_sentence=example_sentence,
		formality_level=formality,
	)
	db.add(entry)
	await db.commit()
	await db.refresh(entry)
	return entry, library


async def list_phrasebook(
	db: AsyncSession, user_id: uuid.UUID, formality_level: str | None
) -> list[tuple[PhrasebookEntry, str | None]]:
	"""Trả (entry, source_reference) — nguồn lấy từ thư viện khi entry còn tham chiếu."""
	query = (
		select(PhrasebookEntry, SlangPhrase.source_reference)
		.outerjoin(SlangPhrase, SlangPhrase.id == PhrasebookEntry.slang_phrase_id)
		.where(PhrasebookEntry.user_id == user_id)
		.order_by(PhrasebookEntry.created_at.desc())
	)
	if formality_level:
		query = query.where(PhrasebookEntry.formality_level == formality_level)
	return [(row[0], row[1]) for row in (await db.execute(query)).all()]
