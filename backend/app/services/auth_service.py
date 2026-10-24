# Business logic Auth: đăng ký, đăng nhập, cấp access/refresh token. Router auth.py chỉ gọi
# các hàm ở đây, không tự thao tác DB.
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.auth_token import AuthToken
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.email_service import send_email


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


GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


async def verify_google_credential(credential: str) -> str | None:
	# Google tự kiểm chữ ký/hạn của ID token; ta chỉ kiểm audience (đúng client_id của app) và email_verified.
	# Trả email chữ thường nếu hợp lệ, None nếu sai; lỗi mạng ném httpx.HTTPError cho router xử lý.
	client_id = get_settings().google_client_id
	if not client_id:
		return None
	async with httpx.AsyncClient(timeout=10) as http:
		response = await http.get(GOOGLE_TOKENINFO_URL, params={"id_token": credential})
	if response.status_code != 200:
		return None
	info = response.json()
	if info.get("aud") != client_id or str(info.get("email_verified")).lower() != "true":
		return None
	return (info.get("email") or "").lower() or None


async def login_with_google(db: AsyncSession, email: str) -> User:
	# Email đã được Google xác minh: tạo user mới nếu chưa có (mật khẩu ngẫu nhiên, không dùng được để đăng nhập)
	# hoặc đánh dấu đã xác minh cho user cũ.
	user = await db.scalar(select(User).where(User.email == email))
	now = datetime.now(timezone.utc)
	if user is None:
		user = User(email=email, password_hash=hash_password(secrets.token_urlsafe(32)), email_verified_at=now)
		db.add(user)
	elif user.email_verified_at is None:
		user.email_verified_at = now
	await db.commit()
	await db.refresh(user)
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


OTP_TTL = timedelta(minutes=10)
OTP_MAX_ATTEMPTS = 5


def _otp_hash(user: User, code: str) -> str:
	# Gắn user_id vào hash: mã 6 số chỉ có 10^6 giá trị nên phải luôn tra theo user, không tra theo mã.
	return hash_refresh_token(f"{user.id}:{code}")


async def _send_otp(db: AsyncSession, user: User, purpose: str) -> None:
	# Thu hồi mã cũ cùng mục đích, tạo mã mới (chỉ lưu hash) và gửi qua email.
	await db.execute(
		update(AuthToken)
		.where(AuthToken.user_id == user.id, AuthToken.purpose == purpose, AuthToken.used_at.is_(None))
		.values(used_at=datetime.now(timezone.utc))
	)
	code = f"{secrets.randbelow(10**6):06d}"
	db.add(
		AuthToken(
			user_id=user.id,
			purpose=purpose,
			token_hash=_otp_hash(user, code),
			expires_at=datetime.now(timezone.utc) + OTP_TTL,
		)
	)
	await db.commit()
	what = "verify your email" if purpose == "verify_email" else "reset your password"
	await send_email(
		user.email,
		f"Your Lumina code: {code}",
		f"Your Lumina code to {what} is {code}. It expires in 10 minutes. If you did not ask for it, ignore this email.",
	)


async def send_verification_email(db: AsyncSession, user: User) -> None:
	await _send_otp(db, user, "verify_email")


async def request_email_flow(db: AsyncSession, email: str, purpose: str) -> None:
	# Endpoint công khai: email không tồn tại / đã xác minh -> im lặng, tránh dò email.
	user = await db.scalar(select(User).where(User.email == email.lower()))
	if user is None or (purpose == "verify_email" and user.email_verified_at is not None):
		return
	await _send_otp(db, user, purpose)


async def _consume_otp(db: AsyncSession, email: str, code: str, purpose: str) -> User | None:
	user = await db.scalar(select(User).where(User.email == email.lower()))
	if user is None:
		return None
	stored = await db.scalar(
		select(AuthToken)
		.where(AuthToken.user_id == user.id, AuthToken.purpose == purpose, AuthToken.used_at.is_(None))
		.order_by(AuthToken.created_at.desc())
	)
	if stored is None or stored.expires_at <= datetime.now(timezone.utc) or stored.attempts >= OTP_MAX_ATTEMPTS:
		return None
	if not hmac.compare_digest(stored.token_hash, _otp_hash(user, code)):
		stored.attempts += 1
		await db.commit()
		return None
	stored.used_at = datetime.now(timezone.utc)
	return user


async def verify_email(db: AsyncSession, email: str, code: str) -> bool:
	user = await _consume_otp(db, email, code, "verify_email")
	if user is None:
		return False
	user.email_verified_at = datetime.now(timezone.utc)
	await db.commit()
	return True


async def reset_password(db: AsyncSession, email: str, code: str, new_password: str) -> bool:
	user = await _consume_otp(db, email, code, "reset_password")
	if user is None:
		return False
	user.password_hash = hash_password(new_password)
	# Đặt lại mật khẩu = nghi ngờ lộ tài khoản: thu hồi mọi phiên đăng nhập cũ.
	await db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(is_revoked=True))
	await db.commit()
	return True
