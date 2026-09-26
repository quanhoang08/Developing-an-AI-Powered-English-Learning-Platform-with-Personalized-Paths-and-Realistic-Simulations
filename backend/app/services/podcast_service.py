# Business logic Podcast (feature-listening.md mục 1-2): tài liệu -> podcast + transcript cấp từ.
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.models.listening import Persona, Podcast, TranscriptSegment
from app.models.notebook import Document
from app.services import llm_service, speech_service
from app.utils.text_extraction import extract_docx_text


async def _load_owned_document(db: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID) -> Document:
	document = await db.scalar(
		select(Document).where(Document.id == document_id, Document.user_id == user_id)
	)
	if document is None:
		raise ValueError("document_not_found")
	if document.status != "ready":
		raise ValueError("document_not_ready")
	return document


async def _resolve_persona(db: AsyncSession, persona_id: uuid.UUID | None) -> Persona | None:
	# Persona sai/không active -> None (dùng giọng mặc định), không lỗi cứng (mục 1.5).
	if persona_id is None:
		return None
	return await db.scalar(
		select(Persona).where(Persona.id == persona_id, Persona.is_active.is_(True))
	)


def _synthesize(script: str, persona: Persona | None) -> bytes:
	if persona is not None and persona.provider == "elevenlabs":
		return speech_service.synthesize_speech(script, persona.voice_id)
	voice = persona.voice_id if persona is not None else None
	return speech_service.synthesize_azure_speech(script, voice)


def _podcast_audio_path(podcast_id: uuid.UUID) -> Path:
	settings = get_settings()
	root = Path(__file__).resolve().parents[2] / settings.storage_audio_dir
	root.mkdir(parents=True, exist_ok=True)
	return root / f"podcast_{podcast_id}.wav"


async def create_podcast(
	db: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID, persona_id: uuid.UUID | None
) -> Podcast:
	"""Tạo podcast đồng bộ trong request (quy mô khóa luận, giống ingest_document). Lỗi dịch vụ
	ngoài -> podcast status='failed' rồi raise, không để lại podcast 'processing' treo mãi."""
	document = await _load_owned_document(db, user_id, document_id)
	persona = await _resolve_persona(db, persona_id)

	podcast_id = uuid.uuid4()
	try:
		if document.source_type == "audio":
			# Audio gốc giữ nguyên giọng thật của người dùng, chỉ bổ sung transcript (mục 1.4).
			audio_path = document.file_path
		else:
			raw_text = await run_in_threadpool(extract_docx_text, document.file_path)
			script = await llm_service.rewrite_for_speech(raw_text)
			audio_bytes = await run_in_threadpool(_synthesize, script, persona)
			dest = _podcast_audio_path(podcast_id)
			dest.write_bytes(audio_bytes)
			audio_path = str(dest)

		transcript = await run_in_threadpool(speech_service.transcribe_audio, audio_path)
		if not transcript.words:
			raise speech_service.SpeechServiceError("empty_transcription")
	except (speech_service.SpeechServiceError, llm_service.AIServiceError):
		db.add(
			Podcast(
				id=podcast_id,
				document_id=document.id,
				script_text="",
				status="failed",
				persona_id=persona.id if persona else None,
			)
		)
		await db.commit()
		raise

	podcast = Podcast(
		id=podcast_id,
		document_id=document.id,
		script_text=transcript.text,
		audio_url=audio_path,
		duration_seconds=round(transcript.duration_ms / 1000),
		persona_id=persona.id if persona else None,
		status="ready",
	)
	db.add(podcast)
	await db.flush()
	for index, word in enumerate(transcript.words):
		db.add(
			TranscriptSegment(
				podcast_id=podcast.id,
				word_index=index,
				word_text=word.text[:100],
				start_time_ms=word.start_ms,
				end_time_ms=word.end_ms,
			)
		)
	await db.commit()
	await db.refresh(podcast)
	return podcast


async def get_owned_podcast(db: AsyncSession, user_id: uuid.UUID, podcast_id: uuid.UUID) -> Podcast:
	# Ownership đi qua documents.user_id; không phải chủ hoặc không tồn tại -> cùng 1 lỗi.
	podcast = await db.scalar(
		select(Podcast)
		.join(Document, Document.id == Podcast.document_id)
		.where(Podcast.id == podcast_id, Document.user_id == user_id)
	)
	if podcast is None:
		raise ValueError("podcast_not_found")
	return podcast


async def list_podcasts(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[Podcast, str]]:
	"""Podcast của user (mới nhất trước) kèm tiêu đề tài liệu nguồn để hiển thị danh sách."""
	result = await db.execute(
		select(Podcast, Document.title)
		.join(Document, Document.id == Podcast.document_id)
		.where(Document.user_id == user_id)
		.order_by(Podcast.created_at.desc())
	)
	return [(row[0], row[1]) for row in result.all()]


async def get_playable_audio_path(db: AsyncSession, user_id: uuid.UUID, podcast_id: uuid.UUID) -> str:
	podcast = await get_owned_podcast(db, user_id, podcast_id)
	if podcast.status != "ready" or not podcast.audio_url or not Path(podcast.audio_url).exists():
		raise ValueError("podcast_audio_not_found")
	return podcast.audio_url


async def get_transcript(
	db: AsyncSession, user_id: uuid.UUID, podcast_id: uuid.UUID
) -> list[TranscriptSegment]:
	podcast = await get_owned_podcast(db, user_id, podcast_id)
	result = await db.execute(
		select(TranscriptSegment)
		.where(TranscriptSegment.podcast_id == podcast.id)
		.order_by(TranscriptSegment.word_index.asc())
	)
	return list(result.scalars().all())
