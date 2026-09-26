import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VocabItem(Base):
	"""Một từ vựng user lưu lại từ Notebook hoặc nguồn web bên ngoài."""

	__tablename__ = "vocab_items"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	document_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
	)
	term: Mapped[str] = mapped_column(String(100))
	ipa: Mapped[str] = mapped_column(String(100), nullable=True)
	part_of_speech: Mapped[str] = mapped_column(String(30), nullable=True)
	definition: Mapped[str] = mapped_column(Text, nullable=True)
	example_sentence: Mapped[str] = mapped_column(Text, nullable=True)
	synonyms: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
	antonyms: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
	source_url: Mapped[str] = mapped_column(Text, nullable=True)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)


class ContextualGuessAttempt(Base):
	"""Một lượt Contextual Guessing: câu điền từ + 4 lựa chọn (correct_option_index ẩn với client)."""

	__tablename__ = "contextual_guess_attempts"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	vocab_item_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("vocab_items.id", ondelete="SET NULL"), nullable=True
	)
	term: Mapped[str] = mapped_column(String(100))
	challenge_sentence: Mapped[str] = mapped_column(Text)
	options: Mapped[list[str]] = mapped_column(JSONB)
	correct_option_index: Mapped[int] = mapped_column(SmallInteger)
	selected_option_index: Mapped[int] = mapped_column(SmallInteger, nullable=True)
	is_correct: Mapped[bool] = mapped_column(Boolean, nullable=True)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)


class CustomStory(Base):
	"""Truyện AI sinh từ danh sách từ vựng đã lưu của user."""

	__tablename__ = "custom_stories"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	vocab_item_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)))
	generated_text: Mapped[str] = mapped_column(Text)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)


class VocabReview(Base):
	"""Trạng thái lặp lại ngắt quãng SM-2 của một VocabItem."""

	__tablename__ = "vocab_reviews"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	vocab_item_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("vocab_items.id", ondelete="CASCADE"),
		unique=True,
	)
	ease_factor: Mapped[float] = mapped_column(Numeric(4, 2), default=2.5)
	interval_days: Mapped[int] = mapped_column(Integer, default=1)
	repetitions: Mapped[int] = mapped_column(Integer, default=0)
	last_grade: Mapped[int] = mapped_column(SmallInteger, nullable=True)
	last_reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
	next_review_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)
