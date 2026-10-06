import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ToeicAttempt(Base):
	"""1 lượt luyện TOEIC-style (migration 20261002_0027). `questions` giữ cả correct_index/explanation_vi lúc
	sinh (không trả cho client trước khi nộp); `picks` + điểm chỉ có sau khi nộp."""

	__tablename__ = "toeic_attempts"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
	part: Mapped[int] = mapped_column(SmallInteger)
	questions: Mapped[list] = mapped_column(JSONB)
	picks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
	correct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
	score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
	submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class ToeicBankUnit(Base):
	"""1 đơn vị đề đã kiểm chứng sẵn trong ngân hàng (migration 20261002_0028): Part 2/5 = 1 câu, Part 6/7 = 1 bài đọc
	+ các câu của nó. `unit` = {"questions": [{prompt, passage, options, correct_index, explanation_vi}]}."""

	__tablename__ = "toeic_bank"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	part: Mapped[int] = mapped_column(SmallInteger)
	unit: Mapped[dict] = mapped_column(JSONB)
	source: Mapped[str] = mapped_column(String(20))  # gemini | ollama: model tác giả
	disabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))  # đánh dấu câu xấu để không phát ra nữa
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
