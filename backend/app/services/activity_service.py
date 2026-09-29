"""Recent activity feed cho Dashboard "Pick up where you left off" (GET /api/activity/recent).

Không có bảng "activity log" chung — lấy trực tiếp từ 4 bảng kết quả của từng kỹ năng (đã có sẵn
timestamp hoàn thành thật), mỗi bảng truy vấn riêng rồi gộp lại theo thời gian, giống cách
review_priority_queue tính lại mỗi lần đọc thay vì duy trì 1 bảng tổng hợp riêng.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listening import DictationAttempt, Podcast
from app.models.notebook import Document
from app.models.reading import GeneratedPassage, ReadingSession
from app.models.speaking import ConversationSession, ConversationTurn, Scenario
from app.models.writing import WritingSubmission

# Số dòng lấy từ MỖI kỹ năng trước khi gộp — đủ để sau khi gộp + cắt về `limit` vẫn phản ánh đúng
# thứ tự thời gian thật (kỹ năng ít hoạt động không bị kỹ năng khác "lấp đầy" toàn bộ danh sách).
_PER_SKILL_FETCH = 10


async def _recent_reading(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
	rows = (
		await db.execute(
			select(ReadingSession, Document.title, GeneratedPassage.title)
			.outerjoin(Document, Document.id == ReadingSession.document_id)
			.outerjoin(GeneratedPassage, GeneratedPassage.id == ReadingSession.generated_passage_id)
			.where(ReadingSession.user_id == user_id, ReadingSession.completed_at.is_not(None))
			.order_by(ReadingSession.completed_at.desc())
			.limit(_PER_SKILL_FETCH)
		)
	).all()
	return [
		{
			"skill": "reading",
			"title": document_title or passage_title or "Reading passage",
			"score": float(session.score) * 100 if session.score is not None else None,
			"created_at": session.completed_at,
		}
		for session, document_title, passage_title in rows
	]


async def _recent_listening(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
	rows = (
		await db.execute(
			select(DictationAttempt, Document.title)
			.join(Podcast, Podcast.id == DictationAttempt.podcast_id)
			.join(Document, Document.id == Podcast.document_id)
			.where(DictationAttempt.user_id == user_id, DictationAttempt.accuracy_score.is_not(None))
			.order_by(DictationAttempt.created_at.desc())
			.limit(_PER_SKILL_FETCH)
		)
	).all()
	return [
		{
			"skill": "listening",
			"title": f"Dictation — {document_title}",
			"score": float(attempt.accuracy_score),
			"created_at": attempt.created_at,
		}
		for attempt, document_title in rows
	]


async def _recent_writing(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
	rows = (
		await db.scalars(
			select(WritingSubmission)
			.where(WritingSubmission.user_id == user_id, WritingSubmission.completed_at.is_not(None))
			.order_by(WritingSubmission.completed_at.desc())
			.limit(_PER_SKILL_FETCH)
		)
	).all()
	return [
		{
			"skill": "writing",
			"title": submission.title or (submission.prompt_text or "Writing submission")[:80],
			"score": float(submission.overall_score) if submission.overall_score is not None else None,
			"created_at": submission.completed_at,
		}
		for submission in rows
	]


async def _recent_speaking(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
	# Chỉ tính phiên đã có ít nhất 1 lượt nói — phiên vừa tạo chưa nói gì chưa phải "hoạt động" để resume.
	has_turn = exists().where(ConversationTurn.conversation_session_id == ConversationSession.id)
	rows = (
		await db.execute(
			select(ConversationSession, Scenario.title)
			.join(Scenario, Scenario.id == ConversationSession.scenario_id)
			.where(ConversationSession.user_id == user_id, has_turn)
			.order_by(ConversationSession.started_at.desc())
			.limit(_PER_SKILL_FETCH)
		)
	).all()
	return [
		{
			"skill": "speaking",
			"title": scenario_title,
			# Chưa có điểm tổng theo phiên (chỉ có điểm từng lượt nói) — None, không suy đoán.
			"score": None,
			"created_at": session.ended_at or session.started_at,
		}
		for session, scenario_title in rows
	]


async def get_recent(db: AsyncSession, user_id: uuid.UUID, limit: int = 5) -> list[dict]:
	"""Tối đa `limit` hoạt động gần nhất, gộp 4 kỹ năng, mới nhất trước."""
	items: list[dict] = []
	for fetch in (_recent_reading, _recent_listening, _recent_writing, _recent_speaking):
		items.extend(await fetch(db, user_id))
	items.sort(key=lambda item: item["created_at"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
	return items[:limit]
