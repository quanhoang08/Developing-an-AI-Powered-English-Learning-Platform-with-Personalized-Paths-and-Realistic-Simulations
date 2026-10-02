# IELTS Speaking giả lập 3 phần (backlog 2.3). Không lưu DB: đề và điểm trả thẳng cho client;
# lượt nói được STT + chấm phát âm bằng đúng hạ tầng của Speaking, không tạo session.
import math
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.speaking import IeltsAttempt
from app.services import llm_service, speaking_service, speech_service
from app.utils.text_metrics import speech_metrics

_ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm", ".ogg"}


def to_band(value) -> float:
	"""Làm tròn về bước 0.5 trong [0, 9] (LLM đôi khi trả 6.7 hoặc 70)."""
	try:
		number = float(value)
	except (TypeError, ValueError):
		return 0.0
	# floor(x+0.5): .25 -> .5 và .75 -> 1.0 như IELTS (round() của Python làm tròn về số chẵn: 6.25 -> 6.0).
	return math.floor(min(max(number, 0.0), 9.0) * 2 + 0.5) / 2


def pronunciation_band(scores: list[float]) -> float | None:
	# ponytail: map tuyến tính điểm Azure 0-100 -> band 0-9, chưa hiệu chỉnh với giám khảo thật.
	if not scores:
		return None
	return to_band(sum(scores) / len(scores) / 100 * 9)


def overall_band(content: list[float], pronunciation: float | None) -> float:
	"""Trung bình các tiêu chí, nhưng phát âm tốt không được nâng overall quá 1 band so với
	trung bình nội dung (trôi chảy/từ vựng/ngữ pháp) — đọc giọng chuẩn mà lạc đề không thể điểm cao."""
	content_mean = sum(content) / len(content)
	if pronunciation is None:
		return to_band(content_mean)
	return to_band(min((sum(content) + pronunciation) / (len(content) + 1), content_mean + 1.0))


async def transcribe_answer(audio: UploadFile, duration_seconds: int | None) -> dict:
	extension = Path(audio.filename or "").suffix.lower()
	if extension not in _ALLOWED_EXTENSIONS:
		raise ValueError("unsupported_audio_type")
	content = await audio.read()
	if not content:
		raise ValueError("empty_audio")
	path = speaking_service._audio_dir() / f"ielts_{uuid.uuid4()}{extension}"
	path.write_bytes(content)
	try:
		text, _ = await run_in_threadpool(speech_service.transcribe_with_fallback, str(path))
	except speech_service.SpeechServiceError as error:
		raise ValueError("stt_service_unavailable") from error
	text = text.strip()
	if not text:
		raise ValueError("empty_transcription")
	pronunciation = await speaking_service._assess_pronunciation(str(path))
	wpm = round(len(text.split()) / duration_seconds * 60) if duration_seconds else None
	return {
		"transcript": text,
		"pronunciation_score": pronunciation.score if pronunciation else None,
		"words_per_minute": wpm,
		**speech_metrics(text),
	}


async def estimate(db: AsyncSession, user_id: uuid.UUID, answers: list[dict], topic: str | None) -> dict:
	result = await llm_service.estimate_ielts_band(answers)
	bands = {
		"fluency_coherence": to_band(result.get("fluency_coherence")),
		"lexical_resource": to_band(result.get("lexical_resource")),
		"grammatical_range": to_band(result.get("grammatical_range")),
	}
	pron = pronunciation_band(
		[a["pronunciation_score"] for a in answers if a.get("pronunciation_score") is not None]
	)
	overall = overall_band(list(bands.values()), pron)
	feedback = (result.get("feedback_vi") or "").strip()
	wpms = [a["words_per_minute"] for a in answers if a.get("words_per_minute")]

	previous = await db.scalar(
		select(IeltsAttempt.overall)
		.where(IeltsAttempt.user_id == user_id)
		.order_by(IeltsAttempt.created_at.desc())
		.limit(1)
	)
	attempt = IeltsAttempt(
		user_id=user_id,
		topic=(topic or "").strip()[:80] or None,
		overall=overall,
		pronunciation=pron,
		words_per_minute=round(sum(wpms) / len(wpms)) if wpms else None,
		feedback_vi=feedback,
		answers=answers,
		**bands,
	)
	db.add(attempt)
	await db.commit()
	return {
		**bands,
		"pronunciation": pron,
		"overall": overall,
		"feedback_vi": feedback,
		"attempt_id": str(attempt.id),
		"previous_overall": float(previous) if previous is not None else None,
	}


async def list_attempts(db: AsyncSession, user_id: uuid.UUID, limit: int = 20) -> list[IeltsAttempt]:
	result = await db.scalars(
		select(IeltsAttempt)
		.where(IeltsAttempt.user_id == user_id)
		.order_by(IeltsAttempt.created_at.desc())
		.limit(limit)
	)
	return list(result)
