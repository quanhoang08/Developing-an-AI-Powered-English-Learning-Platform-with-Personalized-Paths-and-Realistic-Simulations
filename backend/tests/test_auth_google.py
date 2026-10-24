import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import auth as auth_router
from app.services import auth_service


REAL_ASYNC_CLIENT = httpx.AsyncClient  # giữ bản gốc: gọi _fake_google nhiều lần không được lồng lambda


def _fake_google(monkeypatch: pytest.MonkeyPatch, payload: dict, status_code: int = 200) -> None:
    # Thay httpx.AsyncClient trong auth_service bằng client trả sẵn phản hồi tokeninfo, không gọi mạng.
    transport = httpx.MockTransport(lambda request: httpx.Response(status_code, json=payload))
    monkeypatch.setattr(auth_service.httpx, "AsyncClient", lambda **kw: REAL_ASYNC_CLIENT(transport=transport, **kw))
    monkeypatch.setattr(auth_service, "get_settings", lambda: SimpleNamespace(google_client_id="cid"))


def _verify(token: str = "t" * 30) -> str | None:
    return asyncio.run(auth_service.verify_google_credential(token))


def test_verify_accepts_verified_email_for_our_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_google(monkeypatch, {"aud": "cid", "email": "Minh@Gmail.com", "email_verified": "true"})
    assert _verify() == "minh@gmail.com"


def test_verify_rejects_wrong_audience_unverified_email_and_bad_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_google(monkeypatch, {"aud": "other-app", "email": "a@gmail.com", "email_verified": "true"})
    assert _verify() is None
    _fake_google(monkeypatch, {"aud": "cid", "email": "a@gmail.com", "email_verified": "false"})
    assert _verify() is None
    _fake_google(monkeypatch, {"error": "invalid_token"}, status_code=400)
    assert _verify() is None


def test_google_endpoint_503_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_router, "get_settings", lambda: SimpleNamespace(google_client_id=""))
    response = TestClient(app).post("/api/auth/google", json={"credential": "t" * 30})
    assert response.status_code == 503
    assert response.json()["detail"] == "google_not_configured"


def test_gmail_blocked_only_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_router, "get_settings", lambda: SimpleNamespace(require_google_for_gmail=True))
    with pytest.raises(auth_router.HTTPException) as blocked:
        auth_router._require_google_for_gmail("x@gmail.com")
    assert blocked.value.detail == "use_google_signin"
    auth_router._require_google_for_gmail("x@school.edu")  # không phải Gmail: qua
    monkeypatch.setattr(auth_router, "get_settings", lambda: SimpleNamespace(require_google_for_gmail=False))
    auth_router._require_google_for_gmail("x@gmail.com")  # cờ tắt: qua
