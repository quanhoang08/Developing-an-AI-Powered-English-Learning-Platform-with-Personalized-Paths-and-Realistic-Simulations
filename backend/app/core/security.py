# Hàm thuần xử lý mật khẩu (bcrypt) và JWT (access token) — dùng chung cho toàn bộ Auth.
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings


ALGORITHM = "HS256"
# CryptContext quản lý bcrypt và cho phép thay đổi thuật toán trong tương lai.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
	# Chỉ lưu chuỗi hash, tuyệt đối không lưu mật khẩu gốc vào database.
	return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
	# So sánh mật khẩu người dùng nhập với hash đã lưu bằng bcrypt.
	return pwd_context.verify(plain_password, password_hash)


def create_access_token(
	subject: str, expires_delta: timedelta | None = None, client_type: str = "web"
) -> str:
	# Tạo access token ngắn hạn; subject là user id để dependency truy tìm người dùng.
	# client_type ("web"/"extension") để middleware giới hạn phạm vi route của token extension.
	settings = get_settings()
	expires_at = datetime.now(timezone.utc) + (
		expires_delta
		or timedelta(minutes=settings.access_token_expire_minutes)
	)
	payload: dict[str, Any] = {"sub": subject, "exp": expires_at, "client_type": client_type}
	return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def get_token_client_type(token: str) -> str:
	# Token cũ (không có claim) hoặc lỗi/hết hạn -> "web": token lỗi để dependency get_current_user
	# trả 401 như thường, middleware scope chỉ chặn token extension hợp lệ.
	settings = get_settings()
	try:
		payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
	except JWTError:
		return "web"
	return payload.get("client_type") or "web"


def decode_access_token(token: str) -> str | None:
	# Giải mã và kiểm tra chữ ký/thời hạn JWT; token lỗi được chuyển thành None.
	settings = get_settings()
	try:
		payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
	except JWTError:
		return None

	subject = payload.get("sub")
	return subject if isinstance(subject, str) and subject else None
