import asyncio
import re
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.database import get_db
from app.main import app


@pytest.fixture
def postgres_client() -> Generator[TestClient, None, None]:
    # Integration test dùng PostgreSQL thật trong Docker, không dùng database giả lập.
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Override dependency để mọi request test dùng session của database container.
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        yield client
    finally:
        # Xóa override để test khác không bị dùng nhầm session integration.
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())


def test_auth_flow_against_postgres(postgres_client: TestClient) -> None:
    # Email ngẫu nhiên giúp test có thể chạy lặp lại mà không đụng unique constraint.
    email = f"phase3_{uuid.uuid4().hex[:12]}@example.com"

    # Đăng ký user mới và kiểm tra response không làm lộ password hash.
    registered = postgres_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "StrongPass123",
            "target_level": "b1",
        },
    )
    assert registered.status_code == 201
    assert registered.json()["email"] == email
    assert "password_hash" not in registered.json()

    # Đăng nhập để lấy access token và refresh token từ database thật.
    logged_in = postgres_client.post(
        "/api/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert logged_in.status_code == 200
    tokens = logged_in.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    # Dùng access token gọi endpoint riêng tư /users/me.
    current_user = postgres_client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert current_user.status_code == 200
    assert current_user.json()["email"] == email


def test_register_rejects_duplicate_email(postgres_client: TestClient) -> None:
    # Đăng ký lần đầu phải thành công để có bản ghi gốc trong DB thật.
    email = f"phase3_dup_{uuid.uuid4().hex[:12]}@example.com"
    payload = {"email": email, "password": "StrongPass123", "target_level": "b1"}
    first = postgres_client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    # Đăng ký lần hai cùng email phải bị chặn bởi unique constraint qua service.
    second = postgres_client.post("/api/auth/register", json=payload)
    assert second.status_code == 400
    assert second.json()["detail"] == "email_already_registered"


def _register_and_login(client: TestClient, prefix: str) -> tuple[str, dict]:
    email = f"{prefix}_{uuid.uuid4().hex[:12]}@example.com"
    payload = {"email": email, "password": "StrongPass123", "target_level": "b1"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    logged_in = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"})
    return email, logged_in.json()


def test_refresh_rotates_token_and_rejects_reuse(postgres_client: TestClient) -> None:
    _, tokens = _register_and_login(postgres_client, "refresh")

    refreshed = postgres_client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]
    me = postgres_client.get(
        "/api/users/me", headers={"Authorization": f"Bearer {new_tokens['access_token']}"}
    )
    assert me.status_code == 200

    # Token cũ đã bị thu hồi sau khi đổi: dùng lại phải bị từ chối.
    reused = postgres_client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reused.status_code == 401
    assert reused.json()["detail"] == "invalid_refresh_token"


def test_refresh_rejects_unknown_token(postgres_client: TestClient) -> None:
    response = postgres_client.post("/api/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert response.status_code == 401


def test_patch_me_updates_target_level(postgres_client: TestClient) -> None:
    _, tokens = _register_and_login(postgres_client, "patchme")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    updated = postgres_client.patch("/api/users/me", json={"target_level": "c1"}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["target_level"] == "c1"
    assert postgres_client.get("/api/users/me", headers=headers).json()["target_level"] == "c1"

    # Body rỗng không được xóa target_level đã có.
    unchanged = postgres_client.patch("/api/users/me", json={}, headers=headers)
    assert unchanged.json()["target_level"] == "c1"


def test_login_rejects_wrong_password(postgres_client: TestClient) -> None:
    # User thật trong DB nhưng đăng nhập sai mật khẩu phải bị từ chối rõ ràng.
    email = f"phase3_badpw_{uuid.uuid4().hex[:12]}@example.com"
    assert postgres_client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPass123", "target_level": "b1"},
    ).status_code == 201

    wrong_login = postgres_client.post(
        "/api/auth/login",
        json={"email": email, "password": "WrongPassword999"},
    )
    assert wrong_login.status_code == 401
    assert wrong_login.json()["detail"] == "invalid_credentials"


@pytest.fixture
def outbox(monkeypatch) -> list[tuple[str, str]]:
    # Chặn gửi mail thật, gom (to, body) để test lấy link chứa token.
    sent: list[tuple[str, str]] = []

    async def fake_send(to: str, subject: str, body: str) -> None:
        sent.append((to, body))

    monkeypatch.setattr("app.services.auth_service.send_email", fake_send)
    return sent


def _code_from(outbox: list[tuple[str, str]], email: str) -> str:
    body = [b for to, b in outbox if to == email][-1]
    return re.search(r"\b(\d{6})\b", body).group(1)


def _wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


def test_email_verification_flow(postgres_client: TestClient, outbox, monkeypatch) -> None:
    email = f"verify_{uuid.uuid4().hex[:12]}@example.com"
    payload = {"email": email, "password": "StrongPass123"}
    assert postgres_client.post("/api/auth/register", json=payload).status_code == 201
    code = _code_from(outbox, email)

    # Bật bắt buộc xác minh: chưa xác minh thì đăng nhập bị 403.
    monkeypatch.setattr(get_settings(), "require_email_verification", True)
    blocked = postgres_client.post("/api/auth/login", json=payload)
    assert blocked.status_code == 403 and blocked.json()["detail"] == "email_not_verified"

    verify = "/api/auth/verify-email"
    assert postgres_client.post(verify, json={"email": email, "code": _wrong(code)}).status_code == 400
    assert postgres_client.post(verify, json={"email": email, "code": code}).status_code == 204
    assert postgres_client.post("/api/auth/login", json=payload).status_code == 200
    # Mã dùng 1 lần.
    assert postgres_client.post(verify, json={"email": email, "code": code}).status_code == 400


def test_otp_locks_after_too_many_wrong_attempts(postgres_client: TestClient, outbox) -> None:
    email = f"lock_{uuid.uuid4().hex[:12]}@example.com"
    assert postgres_client.post("/api/auth/register", json={"email": email, "password": "StrongPass123"}).status_code == 201
    code = _code_from(outbox, email)
    verify = "/api/auth/verify-email"
    for _ in range(5):
        assert postgres_client.post(verify, json={"email": email, "code": _wrong(code)}).status_code == 400
    # Sau 5 lần sai, ngay cả mã đúng cũng bị khóa: phải xin mã mới.
    assert postgres_client.post(verify, json={"email": email, "code": code}).status_code == 400
    assert postgres_client.post("/api/auth/resend-verification", json={"email": email}).status_code == 204
    assert postgres_client.post(verify, json={"email": email, "code": _code_from(outbox, email)}).status_code == 204


def test_password_reset_flow(postgres_client: TestClient, outbox) -> None:
    email, tokens = _register_and_login(postgres_client, "reset")
    n = len(outbox)

    # Email lạ: vẫn 204 và không gửi mail (không lộ email tồn tại).
    unknown = postgres_client.post("/api/auth/forgot-password", json={"email": "nobody_x@example.com"})
    assert unknown.status_code == 204 and len(outbox) == n

    assert postgres_client.post("/api/auth/forgot-password", json={"email": email}).status_code == 204
    body = {"email": email, "code": _code_from(outbox, email), "new_password": "NewStrongPass456"}
    assert postgres_client.post("/api/auth/reset-password", json=body).status_code == 204

    assert postgres_client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"}).status_code == 401
    assert postgres_client.post("/api/auth/login", json={"email": email, "password": "NewStrongPass456"}).status_code == 200
    # Phiên cũ bị thu hồi, mã reset không dùng lại được.
    assert postgres_client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    assert postgres_client.post("/api/auth/reset-password", json=body).status_code == 400
