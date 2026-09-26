import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RefreshToken(Base):
	# Lưu phiên refresh token dưới dạng hash để có thể thu hồi mà không lưu token thô.
	__tablename__ = "refresh_tokens"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True),
		primary_key=True,
		server_default=text("uuid_generate_v4()"),
	)
	# Token thuộc user nào; xóa user sẽ cascade xóa các token liên quan.
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
	is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
	# 'web' | 'extension' — refresh giữ nguyên loại này để token extension không "nâng cấp" thành web.
	client_type: Mapped[str] = mapped_column(String(20), server_default=text("'web'"), default="web")
	expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)