# Model Module 0 — Adaptive Learning Engine: user_errors (nguồn dữ liệu lỗi), quizzes/quiz_attempts
# (đề động sinh theo điểm yếu) và review_priority_queue (hàng đợi ôn tập tổng hợp).
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# 9 giá trị đề xuất trong api-spec.md mục 9 — vẫn "chưa chốt chính thức" theo
# lumina_context.md mục 4 điểm 1, dùng tạm để validate ở tầng service/CHECK constraint.
ERROR_TYPES = (
	"grammar",
	"vocabulary",
	"spelling",
	"pronunciation",
	"listening_comprehension",
	"reading_comprehension",
	"writing_coherence",
	"communicative_intent",
	"politeness",
)


class UserError(Base):
	"""1 lỗi cụ thể của user, nguồn dữ liệu cho Adaptive Learning Engine (ưu tiên ôn tập).

	Thay thế bảng error_log cũ (generic, đã lỗi thời) theo quyết định lumina_context.md mục
	3.1 — bảng error_log đã bị xoá ở migration 20260924_0015.
	"""

	__tablename__ = "user_errors"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	# quiz_attempt_id: NULL khi lỗi phát sinh ngoài đề Adaptive (Dictation, Writing...); có giá trị
	# khi lỗi ghi từ 1 lượt làm đề động.
	quiz_attempt_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("quiz_attempts.id", ondelete="SET NULL"), nullable=True
	)
	error_type: Mapped[str] = mapped_column(String(30))
	spaced_repetition_level: Mapped[int] = mapped_column(Integer, server_default=text("0"))
	# detail: {source, original_text?, corrected_text?, explanation?} — dữ liệu để sinh câu hỏi luyện tập.
	detail: Mapped[dict] = mapped_column(JSONB, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default=text("now()"))


class Quiz(Base):
	"""Đề kiểm tra động do Adaptive Engine sinh từ lỗi của user (Rearrange the Block không dùng bảng này)."""

	__tablename__ = "quizzes"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	generated_from_error_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
	focus_error_types: Mapped[list[str]] = mapped_column(JSONB, nullable=True)
	questions: Mapped[list[dict]] = mapped_column(JSONB)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default=text("now()"))


class QuizAttempt(Base):
	"""1 lượt làm 1 bộ đề; 1 Quiz có thể được làm lại nhiều lần."""

	__tablename__ = "quiz_attempts"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	quiz_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=True
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	# Rearrange the Block (quiz_id NULL): answers = thứ tự khối user nộp (NULL = bài còn mở),
	# score theo thang 0-1 (partial credit), payload = khối + thứ tự chấp nhận + lỗi nguồn.
	attempt_type: Mapped[str] = mapped_column(String(30), nullable=True)
	is_open_form: Mapped[bool] = mapped_column(Boolean, nullable=True)
	payload: Mapped[dict] = mapped_column(JSONB, nullable=True)
	answers: Mapped[list] = mapped_column(JSONB, nullable=True)
	score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
	completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default=text("now()"))


class ReviewPriorityItem(Base):
	"""Mục trong hàng đợi ôn tập: item_type 'vocab' (item_id = vocab_items.id) hoặc 'error' (user_errors.id)."""

	__tablename__ = "review_priority_queue"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	item_type: Mapped[str] = mapped_column(String(20))
	item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
	priority_score: Mapped[float] = mapped_column(Numeric(6, 2))
	last_calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default=text("now()"))
