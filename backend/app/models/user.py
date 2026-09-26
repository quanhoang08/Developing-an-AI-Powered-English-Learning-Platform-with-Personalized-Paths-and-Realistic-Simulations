import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
	# Ánh xạ bảng users: danh tính, mật khẩu đã hash và trình độ mục tiêu.
	__tablename__ = "users"

	# PostgreSQL tự sinh UUID cho mỗi tài khoản mới.
	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True),
		primary_key=True,
		server_default=text("uuid_generate_v4()"),
	)
	# Email duy nhất được dùng làm định danh đăng nhập.
	email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
	password_hash: Mapped[str] = mapped_column(String(255))
	display_name: Mapped[str] = mapped_column(String(100), nullable=True)
	native_language: Mapped[str] = mapped_column(String(10), default="vi")
	target_level: Mapped[str] = mapped_column(String(10), nullable=True)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)
