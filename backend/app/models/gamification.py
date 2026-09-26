import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Streak(Base):
	"""Chuỗi ngày học liên tục + tổng XP của 1 user (mỗi user đúng 1 dòng, khoá chính user_id).

	total_xp thêm ở migration 0012 — ERD gốc (STREAKS) chưa có cột này; XP cộng cùng lúc với
	streak trong gamification_service.award_activity để hai số luôn khớp nhau.
	"""

	__tablename__ = "streaks"

	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
	)
	current_streak: Mapped[int] = mapped_column(Integer, server_default=text("0"))
	longest_streak: Mapped[int] = mapped_column(Integer, server_default=text("0"))
	# Không dùng `date | None`: SQLAlchemy hiện tại lỗi khi resolve union này trên Python 3.14,
	# các model khác cũng khai báo cột nullable bằng nullable=True.
	last_active_date: Mapped[date] = mapped_column(Date, nullable=True)
	total_xp: Mapped[int] = mapped_column(Integer, server_default=text("0"))


class SkillProgress(Base):
	"""Điểm trung bình động (0-100) + CEFR của từng kỹ năng, mỗi (user, kỹ năng) đúng 1 dòng.

	skill_name: reading | listening | writing | speaking. cefr_level chỉ Writing chấm ra được
	(LLM ước lượng) nên các kỹ năng khác để NULL thay vì tự quy đổi điểm sang CEFR.
	"""

	__tablename__ = "skill_progress"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	skill_name: Mapped[str] = mapped_column(String(30))
	cefr_level: Mapped[str] = mapped_column(String(20), nullable=True)
	score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), nullable=True, server_default=text("now()")
	)
