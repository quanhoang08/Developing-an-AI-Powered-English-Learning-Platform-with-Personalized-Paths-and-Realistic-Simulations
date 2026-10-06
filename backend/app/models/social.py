import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_UUID_PK = dict(primary_key=True, server_default=text("uuid_generate_v4()"))


class VoiceDiaryEntry(Base):
	"""Một bản ghi nhật ký giọng nói <= 60 giây (backlog 4.4); file nằm trong storage/audio."""

	__tablename__ = "voice_diary_entries"

	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **_UUID_PK)
	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
	file_name: Mapped[str] = mapped_column(String(100))
	duration_seconds: Mapped[int] = mapped_column(Integer)
	transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
	words_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Friendship(Base):
	"""Lời mời kết bạn: pending -> accepted (backlog 4.6)."""

	__tablename__ = "friendships"

	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **_UUID_PK)
	requester_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
	addressee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
	status: Mapped[str] = mapped_column(String(10), server_default=text("'pending'"))
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Classroom(Base):
	"""Lớp học: người tạo là giáo viên, học sinh vào bằng join_code (backlog nhóm 5)."""

	__tablename__ = "classes"

	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **_UUID_PK)
	teacher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
	name: Mapped[str] = mapped_column(String(100))
	join_code: Mapped[str] = mapped_column(String(8), unique=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class ClassMember(Base):
	__tablename__ = "class_members"

	class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True)
	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
	joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class ClassAssignment(Base):
	__tablename__ = "class_assignments"

	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **_UUID_PK)
	class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"))
	title: Mapped[str] = mapped_column(String(150))
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	skill: Mapped[str | None] = mapped_column(String(20), nullable=True)
	due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
