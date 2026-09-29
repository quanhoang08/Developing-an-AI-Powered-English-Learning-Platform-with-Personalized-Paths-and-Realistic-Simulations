# Business logic Writing: tạo đề (3 nguồn), nộp bài + chấm điểm qua Gemini.
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notebook import Document, DocumentChunk
from app.models.writing import RephraseRequest, WritingInsight, WritingSubmission
from app.services import adaptive_service, llm_service
from app.services.gamification_service import award_activity

MIN_SUBMISSION_WORDS = 30
# Thang 0-100; ngưỡng đề xuất trong thiet_ke_database.md mục 10, chưa được xác nhận.
COHERENCE_ERROR_THRESHOLD = 60

_DOCUMENT_SUMMARY_PROMPT = "Summarize the main ideas of the uploaded document in your own words."


async def _load_ready_document(db: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID) -> Document:
	# Helper dùng chung: tải document đúng chủ sở hữu và đã ingest xong, nếu không raise lỗi rõ ràng.
	document = await db.scalar(
		select(Document).where(Document.id == document_id, Document.user_id == user_id)
	)
	if document is None:
		raise ValueError("document_not_found")
	if document.status != "ready":
		raise ValueError("document_not_ready")
	return document


async def _load_document_text(db: AsyncSession, document_id: uuid.UUID) -> str:
	# Ghép toàn bộ document_chunks thành 1 khối text để đưa vào prompt sinh đề/chấm điểm.
	result = await db.execute(
		select(DocumentChunk)
		.where(DocumentChunk.document_id == document_id)
		.order_by(DocumentChunk.chunk_index.asc())
		.limit(30)
	)
	chunks = list(result.scalars().all())
	if not chunks:
		raise ValueError("document_has_no_chunks")
	return "\n".join(chunk.content for chunk in chunks)


async def create_submission(
	db: AsyncSession,
	user_id: uuid.UUID,
	source_type: str,
	document_id: uuid.UUID | None,
	prompt_text: str | None,
	certificate_style: str | None,
) -> WritingSubmission:
	"""Tạo writing_submissions với prompt_text cuối cùng theo source_type.

	`extended_topic` bắt buộc document_id hợp lệ (status=ready) — nếu tài liệu chưa có
	document_chunks (chưa ingest xong), báo lỗi nghiệp vụ thay vì để LLM nhận input rỗng.
	"""
	final_prompt = prompt_text

	if source_type == "document_summary":
		await _load_ready_document(db, user_id, document_id)
		final_prompt = _DOCUMENT_SUMMARY_PROMPT
	elif source_type == "extended_topic":
		await _load_ready_document(db, user_id, document_id)
		document_text = await _load_document_text(db, document_id)
		final_prompt = await llm_service.generate_extended_topic_prompt(document_text)
	# free_topic: schema đã bắt buộc prompt_text, dùng thẳng không qua LLM sinh đề.

	submission = WritingSubmission(
		user_id=user_id,
		document_id=document_id,
		source_type=source_type,
		prompt_text=final_prompt,
		certificate_style=certificate_style,
		submitted_text="",
	)
	db.add(submission)
	await db.commit()
	await db.refresh(submission)
	return submission


async def get_owned_submission(
	db: AsyncSession, user_id: uuid.UUID, submission_id: uuid.UUID
) -> WritingSubmission:
	# Tải submission đúng chủ sở hữu — dùng cho cả GET detail lẫn submit.
	submission = await db.scalar(
		select(WritingSubmission).where(
			WritingSubmission.id == submission_id, WritingSubmission.user_id == user_id
		)
	)
	if submission is None:
		raise ValueError("submission_not_found")
	return submission


async def submit_essay(
	db: AsyncSession,
	user_id: uuid.UUID,
	submission_id: uuid.UUID,
	submitted_text: str,
	duration_seconds: int | None = None,
) -> WritingSubmission:
	"""Nộp bài + chấm điểm. document_summary dùng coverage; extended/free_topic dùng rubric.

	Idempotent giống Reading Classic: nộp lại một submission đã completed trả kết quả cũ,
	không gọi lại LLM/tạo insight trùng.
	"""
	submission = await get_owned_submission(db, user_id, submission_id)
	if submission.completed_at is not None:
		return submission

	word_count = len(submitted_text.split())
	if word_count < MIN_SUBMISSION_WORDS:
		raise ValueError("submission_too_short")

	if submission.source_type == "document_summary":
		# document_id về NULL khi user xoá tài liệu sau lúc tạo đề (FK ON DELETE SET NULL).
		if submission.document_id is None:
			raise ValueError("document_not_found")
		document_text = await _load_document_text(db, submission.document_id)
		graded = await llm_service.grade_document_summary(document_text, submitted_text)
		rubric_scores = None
	else:
		graded = await llm_service.grade_open_essay(submission.prompt_text, submitted_text)

	if submission.source_type != "document_summary":
		rubric_scores = {
			"task_response": graded["task_response"],
			"coherence_cohesion": graded["coherence_cohesion"],
			"lexical_resource": graded["lexical_resource"],
			"grammatical_range_accuracy": graded["grammatical_range_accuracy"],
		}
		# Nguồn duy nhất của error_type 'writing_coherence' (thiet_ke_database.md mục 10/12).
		if rubric_scores["coherence_cohesion"] < COHERENCE_ERROR_THRESHOLD:
			adaptive_service.record_error(
				db,
				user_id,
				"writing_coherence",
				{
					"source": "writing",
					"submission_id": str(submission.id),
					"coherence_cohesion": rubric_scores["coherence_cohesion"],
				},
			)

	submission.submitted_text = submitted_text
	submission.overall_score = graded["overall_score"]
	submission.cefr_level = graded["cefr_level"]
	submission.ielts_band = graded["ielts_band"]
	submission.rubric_scores = rubric_scores
	submission.completed_at = datetime.now(timezone.utc)

	for insight in graded.get("insights", []):
		db.add(
			WritingInsight(
				writing_submission_id=submission.id,
				insight_type=insight["insight_type"],
				title=insight["title"],
				description=insight["description"],
				original_text=insight.get("original_text"),
				suggested_text=insight.get("suggested_text"),
			)
		)

	# Nộp lại submission đã completed return sớm ở đầu hàm nên chỉ lần chấm đầu được cộng XP.
	await award_activity(
		db, user_id, "writing_submitted", score=graded["overall_score"], cefr_level=graded["cefr_level"],
		duration_seconds=duration_seconds,
	)
	await db.commit()
	await db.refresh(submission)
	return submission


async def list_insights(db: AsyncSession, submission_id: uuid.UUID) -> list[WritingInsight]:
	# Lấy danh sách gợi ý/lỗi Gemini đã ghi cho 1 submission, để trả về trong response submit.
	result = await db.execute(
		select(WritingInsight)
		.where(WritingInsight.writing_submission_id == submission_id)
		.order_by(WritingInsight.created_at.asc())
	)
	return list(result.scalars().all())


async def check_grammar(
	db: AsyncSession, user_id: uuid.UUID, submission_id: uuid.UUID | None, raw_text: str | None
) -> list[dict]:
	"""Inline Grammar Correction. submission_id → chấm bài đã có, LƯU kết quả vào
	writing_insights. raw_text → chấm nhanh preview, KHÔNG lưu gì (feature-writing.md mục 2.3).
	"""
	if submission_id is not None:
		submission = await get_owned_submission(db, user_id, submission_id)
		text = submission.submitted_text
	else:
		submission = None
		text = raw_text

	if not text or not text.strip():
		raise ValueError("no_text_to_check")

	errors = await llm_service.check_grammar(text)

	if submission is not None:
		for error in errors:
			db.add(
				WritingInsight(
					writing_submission_id=submission.id,
					insight_type="grammar",
					title="Grammar/spelling issue",
					description=error["explanation"],
					original_text=error["original_text"],
					suggested_text=error["suggested_text"],
					error_start_offset=error["offset_start"],
					error_end_offset=error["offset_end"],
					rule=error["explanation"],
				)
			)
		await db.commit()

	return errors


async def rephrase(
	db: AsyncSession, user_id: uuid.UUID, submission_id: uuid.UUID, sentence_text: str | None
) -> tuple[str, list[RephraseRequest]]:
	"""AI Rephrase trên 1 câu của bài đã nộp — sentence_text rỗng thì để model tự chọn câu yếu nhất."""
	submission = await get_owned_submission(db, user_id, submission_id)
	if not submission.submitted_text.strip():
		raise ValueError("submission_not_submitted_yet")

	result = await llm_service.rephrase_sentence(submission.submitted_text, sentence_text)

	rows = []
	for suggestion in result["suggestions"]:
		row = RephraseRequest(
			writing_submission_id=submission.id,
			original_text=result["original_sentence"],
			rephrased_text=suggestion["text"],
			explanation=suggestion["explanation"],
		)
		db.add(row)
		rows.append(row)
	await db.commit()
	for row in rows:
		await db.refresh(row)
	return result["original_sentence"], rows


async def suggest_prompt(
	db: AsyncSession,
	user_id: uuid.UUID,
	source_type: str,
	document_id: uuid.UUID | None,
	topic: str | None,
	certificate_style: str | None,
	level: str,
) -> dict:
	"""Sinh/chọn đề bài TRƯỚC khi tạo submission (feature-writing.md mục 1.1-1.2).

	Trả `{prompt_text, source_type}` cho mọi nhánh, trừ free_topic+certificate_style (không
	kèm topic) trả `{prompt_options: [...]}` — 2-3 lựa chọn, CHƯA tạo submission.
	"""
	if source_type == "document_summary":
		await _load_ready_document(db, user_id, document_id)
		return {"prompt_text": _DOCUMENT_SUMMARY_PROMPT, "source_type": source_type}

	if source_type == "extended_topic":
		await _load_ready_document(db, user_id, document_id)
		document_text = await _load_document_text(db, document_id)
		prompt_text = await llm_service.generate_extended_topic_prompt(document_text)
		return {"prompt_text": prompt_text, "source_type": source_type}

	# free_topic
	if topic:
		return {"prompt_text": topic, "source_type": source_type}

	options = await llm_service.generate_free_topic_prompt_options(certificate_style, level)
	return {"prompt_options": options}
