import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuthToken(Base):
	# Mã OTP 6 số dùng 1 lần gửi qua email (xác minh email / đặt lại mật khẩu); chỉ lưu hash.
	__tablename__ = "auth_tokens"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
	purpose: Mapped[str] = mapped_column(String(20))  # 'verify_email' | 'reset_password'
	token_hash: Mapped[str] = mapped_column(String(255))  # hash(user_id:mã OTP)
	expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
	used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
