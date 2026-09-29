# Business logic Listening — Dictation (feature-listening.md mục 3). Podcast creation nằm ở
# podcast_service.py; Dictation chỉ ĐỌC podcast/transcript_segments do service đó tạo ra.
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.listening import DictationAttempt, Podcast, TranscriptSegment
from app.models.notebook import Document
from app.services import adaptive_service, speech_service
from app.services.gamification_service import award_activity
from app.utils.dictation_grading import diff_dictation
from app.utils.word_frequency import tag_reference_words

# Giữa khoảng 15-30 giây theo feature-listening.md mục 3.2 ("mặc định hệ thống tự chọn 1 đoạn
# ~15-30 giây") khi client không truyền segment_range.
DEFAULT_SEGMENT_SECONDS = 20
_SENTENCE_END_CHARS = (".", "!", "?")


def _audio_segment_path(attempt_id: uuid.UUID) -> Path:
	settings = get_settings()
	root = Path(__file__).resolve().parents[2] / settings.storage_audio_dir
	root.mkdir(parents=True, exist_ok=True)
	return root / f"dictation_{attempt_id}.wav"


async def _load_owned_podcast(db: AsyncSession, user_id: uuid.UUID, podcast_id: uuid.UUID) -> Podcast:
	# Podcast không có user_id trực tiếp — ownership đi qua documents.user_id (podcast luôn
	# sinh từ 1 document của user). "podcast_not_found" dùng chung cho cả không tồn tại lẫn
	# không phải chủ sở hữu, tránh lộ thông tin (giống pattern submission_not_found ở Writing).
	podcast = await db.scalar(
		select(Podcast).join(Document, Document.id == Podcast.document_id).where(
			Podcast.id == podcast_id, Document.user_id == user_id
		)
	)
	if podcast is None:
		raise ValueError("podcast_not_found")
	if podcast.status != "ready":
		raise ValueError("podcast_not_ready")
	return podcast


async def _load_transcript_words(db: AsyncSession, podcast_id: uuid.UUID) -> list[TranscriptSegment]:
	result = await db.execute(
		select(TranscriptSegment)
		.where(TranscriptSegment.podcast_id == podcast_id)
		.order_by(TranscriptSegment.word_index.asc())
	)
	words = list(result.scalars().all())
	if not words:
		raise ValueError("podcast_has_no_transcript")
	return words


def _sentence_start_indices(word_texts: list[str]) -> set[int]:
	# Từ đầu tiên của podcast luôn coi là đầu câu; sau đó 1 từ là đầu câu nếu từ liền trước
	# kết thúc bằng dấu chấm câu kết câu (dùng cho gắn nhãn tên riêng — is_proper_noun không
	# tính viết hoa đầu câu là dấu hiệu tên riêng, feature-listening.md mục 3.5).
	indices = {0}
	for index in range(len(word_texts) - 1):
		if word_texts[index].rstrip()[-1:] in _SENTENCE_END_CHARS:
			indices.add(index + 1)
	return indices


def _select_segment_range(
	words: list[TranscriptSegment], requested_ms: tuple[int, int] | None
) -> tuple[int, int]:
	"""Trả về (start_word_index, end_word_index) — CHỈ SỐ TUYỆT ĐỐI trong words (giả định
	word_index liên tục từ 0, đúng cách podcast_service sẽ ghi khi sinh transcript)."""
	if requested_ms is not None:
		start_ms, end_ms = requested_ms
		matching = [word.word_index for word in words if start_ms <= word.start_time_ms < end_ms]
		if not matching:
			raise ValueError("segment_range_has_no_words")
		return min(matching), max(matching)

	# Mặc định: ~20s tính từ từ đầu tiên của podcast (không chọn ngẫu nhiên — ưu tiên kết quả
	# tái lập được cho test/demo hơn là đa dạng hoá vị trí giữa các lần gọi).
	target_end_ms = words[0].start_time_ms + DEFAULT_SEGMENT_SECONDS * 1000
	end_index = words[-1].word_index
	for word in words:
		if word.start_time_ms > target_end_ms:
			end_index = max(word.word_index - 1, words[0].word_index)
			break
	return words[0].word_index, end_index


async def create_dictation_attempt(
	db: AsyncSession,
	user_id: uuid.UUID,
	podcast_id: uuid.UUID,
	segment_range_ms: tuple[int, int] | None,
) -> DictationAttempt:
	"""Tạo 1 lượt Dictation: chọn đoạn, gắn nhãn từ hiếm/tên riêng, cắt audio, LƯU LẠI —
	KHÔNG trả text gốc (feature-listening.md mục 3.3 bước 1-2)."""
	podcast = await _load_owned_podcast(db, user_id, podcast_id)
	words = await _load_transcript_words(db, podcast.id)

	start_index, end_index = _select_segment_range(words, segment_range_ms)
	word_by_index = {word.word_index: word for word in words}
	segment_words = [word_by_index[i].word_text for i in range(start_index, end_index + 1)]

	sentence_starts_full = _sentence_start_indices([word.word_text for word in words])
	segment_sentence_starts = {
		index - start_index for index in sentence_starts_full if start_index <= index <= end_index
	}
	reference_tags = tag_reference_words(segment_words, segment_sentence_starts)

	attempt_id = uuid.uuid4()
	dest_path = _audio_segment_path(attempt_id)
	start_ms = word_by_index[start_index].start_time_ms
	end_ms = word_by_index[end_index].end_time_ms
	# podcast.audio_url hiện là filesystem path cục bộ (giống documents.file_path) — chưa có
	# route static-file-serving thật, sẽ nối khi Podcast creation + frontend Listening view
	# được xây (xem lumina_context.md, Podcast phụ thuộc ElevenLabs/Azure key chưa có).
	speech_service.slice_wav_segment(podcast.audio_url, start_ms, end_ms, str(dest_path))

	attempt = DictationAttempt(
		id=attempt_id,
		podcast_id=podcast.id,
		user_id=user_id,
		start_word_index=start_index,
		end_word_index=end_index,
		audio_segment_path=str(dest_path),
		reference_word_tags=reference_tags,
		# user_input_text NOT NULL trong DB — set rỗng tường minh, không dựa vào server_default
		# ngầm (giống cách WritingSubmission.create_submission set submitted_text="").
		user_input_text="",
	)
	db.add(attempt)
	await db.commit()
	await db.refresh(attempt)
	return attempt


async def get_owned_attempt(db: AsyncSession, user_id: uuid.UUID, attempt_id: uuid.UUID) -> DictationAttempt:
	attempt = await db.scalar(
		select(DictationAttempt).where(
			DictationAttempt.id == attempt_id, DictationAttempt.user_id == user_id
		)
	)
	if attempt is None:
		raise ValueError("dictation_attempt_not_found")
	return attempt


async def submit_dictation_attempt(
	db: AsyncSession,
	user_id: uuid.UUID,
	attempt_id: uuid.UUID,
	transcribed_text: str,
	duration_seconds: int | None = None,
) -> DictationAttempt:
	"""Chấm 1 lượt Dictation, ghi user_errors, LƯU kết quả. Idempotent giống Writing/Reading:
	nộp lại 1 attempt đã chấm trả đúng kết quả cũ, không chấm lại/ghi trùng user_errors."""
	attempt = await get_owned_attempt(db, user_id, attempt_id)
	if attempt.diff_result is not None:
		return attempt

	words = await _load_transcript_words(db, attempt.podcast_id)
	reference_words = [
		word.word_text for word in words if attempt.start_word_index <= word.word_index <= attempt.end_word_index
	]

	errors, score = diff_dictation(reference_words, attempt.reference_word_tags, transcribed_text)

	# Chỉ ghi user_errors cho missing/wrong đã phân loại được (error_type is not None) — lỗi
	# "extra" không có từ gốc để so khớp ngữ âm/độ hiếm, xem dictation_grading.diff_dictation.
	for error in errors:
		if error["error_type"] is not None:
			adaptive_service.record_error(
				db,
				user_id,
				error["error_type"],
				{"source": "dictation", "original_text": error["word"], "explanation": f"{error['type']} word"},
			)

	attempt.user_input_text = transcribed_text
	attempt.diff_result = errors
	attempt.accuracy_score = score
	# Attempt đã chấm return sớm (diff_result is not None) nên chỉ lần chấm đầu được cộng XP.
	await award_activity(db, user_id, "dictation_completed", score=score, duration_seconds=duration_seconds)
	await db.commit()
	await db.refresh(attempt)
	return attempt
