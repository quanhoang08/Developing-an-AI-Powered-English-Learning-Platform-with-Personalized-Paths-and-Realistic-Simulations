import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GeneratedPassage(Base):
	"""Đoạn văn dùng cho Skim & Scan — do AI sinh tự do theo topic, hoặc trích từ 1
	document đã upload khi source_document_id được set (xem reading_service)."""

	__tablename__ = "generated_passages"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	# Nullable: chỉ set khi passage được trích từ tài liệu user đã upload (không phải AI tự sinh).
	source_document_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
	)
	topic: Mapped[str] = mapped_column(String(100), nullable=True)
	level: Mapped[str] = mapped_column(String(10), nullable=True)
	title: Mapped[str] = mapped_column(String(255), nullable=True)
	content: Mapped[str] = mapped_column(Text)
	read_time_label: Mapped[str] = mapped_column(String(20), nullable=True)
	word_count_label: Mapped[str] = mapped_column(String(20), nullable=True)
	target_vocab_words: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)


class ReadingSession(Base):
	"""Một lượt Reading của user — hỗ trợ mode classic và skim_scan."""

	__tablename__ = "reading_sessions"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	document_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
	)
	generated_passage_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("generated_passages.id", ondelete="CASCADE"),
		nullable=True,
	)
	mode: Mapped[str] = mapped_column(String(20))
	score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
	time_taken_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)
	completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class ReadingAnswer(Base):
	"""Câu hỏi và đáp án của một ReadingSession, kèm citation chunk."""

	__tablename__ = "reading_answers"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	reading_session_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("reading_sessions.id", ondelete="CASCADE")
	)
	question: Mapped[str] = mapped_column(Text)
	options: Mapped[list[str]] = mapped_column(JSON)
	correct_option_index: Mapped[int] = mapped_column(SmallInteger)
	selected_option_index: Mapped[int] = mapped_column(SmallInteger, nullable=True)
	is_correct: Mapped[bool] = mapped_column(Boolean, nullable=True)
	# Chỉ câu True/False/Not Given có; chỉ trả cho client sau khi nộp bài.
	explanation: Mapped[str] = mapped_column(Text, nullable=True)
	source_chunk_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True
	)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)
