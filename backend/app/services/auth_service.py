# Business logic Auth: đăng ký, đăng nhập, cấp access/refresh token. Router auth.py chỉ gọi
# các hàm ở đây, không tự thao tác DB.
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.refresh_token import RefreshToken
from app.models.user import User


def hash_refresh_token(token: str) -> str:
	# SHA-256 đủ để đối chiếu refresh token ngẫu nhiên mà không lưu token gốc.
	return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_refresh_token() -> str:
	# Sinh refresh token mật mã ngẫu nhiên để client giữ, database chỉ lưu hash.
	return secrets.token_urlsafe(48)


async def register_user(
	db: AsyncSession,
	email: str,
	password: str,
	target_level: str | None,
) -> User:
	# Kiểm tra email trùng, hash mật khẩu và tạo user trong một transaction.
	result = await db.execute(select(User).where(User.email == email.lower()))
	if result.scalar_one_or_none() is not None:
		raise ValueError("email_already_registered")

	user = User(
		email=email.lower(),
		password_hash=hash_password(password),
		target_level=target_level,
	)
	db.add(user)
	await db.commit()
	await db.refresh(user)
	return user


async def authenticate_user(
	db: AsyncSession, email: str, password: str
) -> User | None:
	# Xác thực email/mật khẩu; trả None chung cho mọi lỗi để không lộ email tồn tại.
	result = await db.execute(select(User).where(User.email == email.lower()))
	user = result.scalar_one_or_none()
	if user is None or not verify_password(password, user.password_hash):
		return None
	return user


async def rotate_refresh_token(db: AsyncSession, refresh_token: str) -> tuple[str, str] | None:
	# Refresh token dùng 1 lần: hợp lệ thì thu hồi token cũ và cấp cặp mới; sai/hết hạn/đã thu hồi → None.
	stored = await db.scalar(
		select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
	)
	if stored is None or stored.is_revoked or stored.expires_at <= datetime.now(timezone.utc):
		return None
	user = await db.get(User, stored.user_id)
	if user is None:
		return None
	stored.is_revoked = True
	return await create_token_pair(db, user, stored.client_type)


async def create_token_pair(db: AsyncSession, user: User, client_type: str = "web") -> tuple[str, str]:
	# Cấp access token dùng ngắn hạn và refresh token lưu hash để thu hồi về sau.
	settings = get_settings()
	access_token = create_access_token(str(user.id), client_type=client_type)
	refresh_token = issue_refresh_token()
	db.add(
		RefreshToken(
			user_id=user.id,
			client_type=client_type,
			token_hash=hash_refresh_token(refresh_token),
			expires_at=datetime.now(timezone.utc)
			+ timedelta(days=settings.refresh_token_expire_days),
		)
	)
	await db.commit()
	return access_token, refresh_token
