from fastapi.testclient import TestClient
from datetime import timedelta

from app.core.config import get_settings
from app.main import app
from app.core.security import (
	create_access_token,
	decode_access_token,
	hash_password,
	verify_password,
)
from app.schemas.auth import RegisterRequest
from pydantic import ValidationError


# TestClient gọi FastAPI trực tiếp, không cần khởi động uvicorn riêng.
client = TestClient(app)


def test_health_check() -> None:
	# Health endpoint phải trả trạng thái và môi trường hiện tại.
	response = client.get("/health")

	assert response.status_code == 200
	assert response.json() == {
		"status": "ok",
		# Môi trường do biến ENV quyết định (container chạy production), không cố định "development".
		"environment": get_settings().environment,
	}


def test_password_hash_is_verifiable_without_storing_plaintext() -> None:
	# Kiểm tra mật khẩu gốc không được lưu trực tiếp và verify hoạt động đúng.
	password = "correct horse battery staple"
	password_hash = hash_password(password)

	assert password_hash != password
	assert verify_password(password, password_hash)
	assert not verify_password("wrong password", password_hash)


def test_access_token_round_trip_and_expiration() -> None:
	# JWT hợp lệ phải decode được; token hết hạn phải bị từ chối.
	token = create_access_token("user-123")

	assert decode_access_token(token) == "user-123"

	expired_token = create_access_token("user-123", timedelta(seconds=-1))
	assert decode_access_token(expired_token) is None


def test_current_user_requires_bearer_token() -> None:
	# Endpoint riêng tư phải từ chối request không có Authorization header.
	response = client.get("/api/users/me")

	assert response.status_code == 401


def test_register_rejects_short_password() -> None:
	# Schema phải chặn mật khẩu ngắn trước khi request chạm database.
	try:
		RegisterRequest(email="learner@example.com", password="short")
	except ValidationError as error:
		assert "String should have at least 8 characters" in str(error)
	else:
		raise AssertionError("short password should fail schema validation")

