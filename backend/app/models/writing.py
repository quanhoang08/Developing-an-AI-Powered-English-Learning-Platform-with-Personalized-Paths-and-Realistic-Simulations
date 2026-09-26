import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WritingSubmission(Base):
	"""Một bài luận (document_summary/extended_topic/free_topic) và kết quả chấm."""

	__tablename__ = "writing_submissions"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	document_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
	)
	source_type: Mapped[str] = mapped_column(String(20))
	prompt_text: Mapped[str] = mapped_column(Text, nullable=True)
	certificate_style: Mapped[str] = mapped_column(String(20), nullable=True)
	title: Mapped[str] = mapped_column(String(255), nullable=True)
	submitted_text: Mapped[str] = mapped_column(Text)
	overall_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
	cefr_level: Mapped[str] = mapped_column(String(15), nullable=True)
	ielts_band: Mapped[str] = mapped_column(String(15), nullable=True)
	# rubric_scores chỉ có giá trị với extended_topic/free_topic; document_summary chấm
	# theo coverage nên field này luôn NULL (xem writing_service.grade_submission).
	rubric_scores: Mapped[dict] = mapped_column(JSONB, nullable=True)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)
	completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class WritingInsight(Base):
	"""Gợi ý/lỗi phát hiện trong một bài luận (grammar/vocabulary/style)."""

	__tablename__ = "writing_insights"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	writing_submission_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("writing_submissions.id", ondelete="CASCADE")
	)
	insight_type: Mapped[str] = mapped_column(String(20))
	title: Mapped[str] = mapped_column(String(150))
	description: Mapped[str] = mapped_column(Text)
	original_text: Mapped[str] = mapped_column(Text, nullable=True)
	suggested_text: Mapped[str] = mapped_column(Text, nullable=True)
	error_start_offset: Mapped[int] = mapped_column(Integer, nullable=True)
	error_end_offset: Mapped[int] = mapped_column(Integer, nullable=True)
	rule: Mapped[str] = mapped_column(Text, nullable=True)
	synonyms: Mapped[list[str]] = mapped_column(JSONB, nullable=True)
	suggestion: Mapped[str] = mapped_column(Text, nullable=True)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)


class RephraseRequest(Base):
	"""Một phương án viết lại câu (AI Rephrase) — 1 row = 1 phương án gợi ý."""

	__tablename__ = "rephrase_requests"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	writing_submission_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("writing_submissions.id", ondelete="CASCADE")
	)
	original_text: Mapped[str] = mapped_column(Text)
	rephrased_text: Mapped[str] = mapped_column(Text)
	explanation: Mapped[str] = mapped_column(Text, nullable=True)
	style_target: Mapped[str] = mapped_column(String(20), nullable=True)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)
