import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GrammarAttempt(Base):
	"""1 lượt làm bản đồ ngữ pháp (migration 20261003_0029). `topic` NULL = test đầu vào trộn mọi chủ điểm;
	`by_topic` = {chủ điểm: {correct, total}}."""

	__tablename__ = "grammar_attempts"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
	topic: Mapped[str | None] = mapped_column(String(30), nullable=True)
	score: Mapped[int] = mapped_column(Integer)
	total: Mapped[int] = mapped_column(Integer)
	by_topic: Mapped[dict] = mapped_column(JSONB)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
