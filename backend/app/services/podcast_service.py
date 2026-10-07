# Business logic Podcast (feature-listening.md mục 1-2): tài liệu -> podcast + transcript cấp từ.
import re
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from datetime import datetime, timezone

from app.models.listening import ListeningQuizAttempt, Persona, Podcast, TranscriptSegment
from app.models.notebook import Document
from app.services import adaptive_service, llm_service, speech_service
from app.services.gamification_service import award_activity
from app.utils.text_extraction import extract_text


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
			# Record audio lịch sử (Notebook giờ chỉ nhận docx/doc/pdf): giữ giọng gốc, chỉ bổ sung transcript.
			audio_path = document.file_path
		else:
			raw_text = await run_in_threadpool(extract_text, document.file_path)
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


_MIN_QUOTE_OVERLAP = 0.6


def _norm(word: str) -> str:
	return "".join(ch for ch in word.lower() if ch.isalnum())


def locate_quote(word_texts: list[str], quote: str) -> tuple[int, int] | None:
	"""Tìm đoạn transcript khớp nhất với câu trích của LLM -> (chỉ số từ đầu, từ cuối).

	So theo tập từ trong cửa sổ cùng độ dài (chịu được STT nghe sai vài từ); dưới 60% trùng -> None.
	"""
	quote_tokens = [t for t in map(_norm, quote.split()) if t]
	words = [_norm(w) for w in word_texts]
	size = len(quote_tokens)
	if size == 0 or size > len(words):
		return None
	wanted = set(quote_tokens)
	best_start, best_score, best_hits = 0, (-1, -1), 0
	for start in range(len(words) - size + 1):
		window = words[start : start + size]
		hits = len(wanted.intersection(window))
		# Hòa số từ trùng -> ưu tiên cửa sổ khớp đúng vị trí từng từ.
		score = (hits, sum(a == b for a, b in zip(window, quote_tokens)))
		if score > best_score:
			best_start, best_score, best_hits = start, score, hits
	if best_hits / len(wanted) < _MIN_QUOTE_OVERLAP:
		return None
	return best_start, best_start + size - 1


async def generate_comprehension(
	db: AsyncSession, user_id: uuid.UUID, podcast_id: uuid.UUID, num_questions: int
) -> tuple[ListeningQuizAttempt, list[dict]]:
	"""Câu hỏi nghe hiểu từ transcript, kèm mốc thời gian đoạn chứa đáp án (backlog 2.2).

	Lưu thành 1 listening_quiz_attempts (chưa nộp); chấm khi gọi submit_quiz.
	"""
	podcast = await get_owned_podcast(db, user_id, podcast_id)
	if podcast.status != "ready":
		raise ValueError("podcast_not_ready")
	words = await get_transcript(db, user_id, podcast_id)
	if not words:
		raise ValueError("podcast_has_no_transcript")
	texts = [w.word_text for w in words]
	raw = await llm_service.generate_listening_questions(" ".join(texts), num_questions)

	questions = []
	for item in raw:
		options = item.get("options") or []
		if len(options) != 4 or not 0 <= item.get("correct_index", -1) < 4:
			continue  # LLM 7-8B đôi khi sinh sai số lựa chọn -> bỏ câu hỏng thay vì trả dữ liệu lệch.
		span = locate_quote(texts, item["evidence_quote"])
		# Model đôi khi vẫn viết "option 2" dù prompt cấm -> đổi thành chữ của lựa chọn đó (người học không thấy số).
		trap_note = re.sub(
			r"\b[Oo]ption ([1-4])\b",
			lambda m: f'"{options[int(m.group(1)) - 1]}"' if 1 <= int(m.group(1)) <= 4 else m.group(0),
			item["trap_note"],
		)
		questions.append(
			{
				"question": item["question"],
				"options": options,
				"correct_index": item["correct_index"],
				"trap_note": trap_note,
				"evidence_text": " ".join(texts[span[0] : span[1] + 1]) if span else item["evidence_quote"],
				"evidence_start_ms": words[span[0]].start_time_ms if span else None,
				"evidence_end_ms": words[span[1]].end_time_ms if span else None,
			}
		)
	if not questions:
		raise llm_service.AIServiceError("no valid questions generated", "ai_bad_output")
	attempt = ListeningQuizAttempt(user_id=user_id, podcast_id=podcast.id, questions=questions)
	db.add(attempt)
	await db.commit()
	return attempt, questions


async def submit_quiz(
	db: AsyncSession,
	user_id: uuid.UUID,
	attempt_id: uuid.UUID,
	picks: list[int | None],
	duration_seconds: int | None = None,
) -> ListeningQuizAttempt:
	"""Chấm quiz ở server, ghi user_errors cho câu sai, cộng XP. Idempotent: nộp lại trả kết quả cũ."""
	attempt = await db.scalar(
		select(ListeningQuizAttempt).where(
			ListeningQuizAttempt.id == attempt_id, ListeningQuizAttempt.user_id == user_id
		)
	)
	if attempt is None:
		raise ValueError("quiz_not_found")
	if attempt.submitted_at is not None:
		return attempt
	if len(picks) != len(attempt.questions):
		raise ValueError("picks_length_mismatch")

	correct_count = 0
	for item, pick in zip(attempt.questions, picks):
		if pick == item["correct_index"]:
			correct_count += 1
			continue
		chosen = item["options"][pick] if isinstance(pick, int) and 0 <= pick < 4 else None
		adaptive_service.record_error(
			db,
			user_id,
			"listening_comprehension",
			{
				"source": "listening_quiz",
				"question": item["question"],
				"original_text": chosen or "(no answer)",
				"corrected_text": item["options"][item["correct_index"]],
				"explanation": item["trap_note"],
				"evidence_text": item["evidence_text"],
			},
		)
	score = round(correct_count / len(attempt.questions) * 100, 2)
	attempt.picks = picks
	attempt.correct_count = correct_count
	attempt.score = score
	attempt.submitted_at = datetime.now(timezone.utc)
	await award_activity(
		db, user_id, "listening_quiz_completed", score=score, duration_seconds=duration_seconds
	)
	await db.commit()
	await db.refresh(attempt)
	return attempt


async def list_quizzes(db: AsyncSession, user_id: uuid.UUID, limit: int = 20) -> list[tuple[ListeningQuizAttempt, str]]:
	result = await db.execute(
		select(ListeningQuizAttempt, Document.title)
		.join(Podcast, Podcast.id == ListeningQuizAttempt.podcast_id)
		.join(Document, Document.id == Podcast.document_id)
		.where(ListeningQuizAttempt.user_id == user_id, ListeningQuizAttempt.submitted_at.is_not(None))
		.order_by(ListeningQuizAttempt.created_at.desc())
		.limit(limit)
	)
	return [(row[0], row[1]) for row in result.all()]
