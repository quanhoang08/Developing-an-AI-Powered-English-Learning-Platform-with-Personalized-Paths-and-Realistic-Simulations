import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.extension_scope import is_extension_allowed
from app.core.security import create_access_token
from app.main import app
from tests.test_rearrange_integration import client, session_factory  # noqa: F401

# Phần không cần DB: route lạ (404) chứng minh request đi qua middleware mà không chạm route/DB.
# Các test *_integration cần Postgres thật (cột refresh_tokens.client_type — migration 0017).


def _bearer(client_type: str | None) -> dict:
    token = (
        create_access_token("00000000-0000-0000-0000-000000000000", client_type=client_type)
        if client_type
        else create_access_token("00000000-0000-0000-0000-000000000000")
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    "path, allowed",
    [
        ("/api/reading/lookup", True),
        ("/api/vocab", True),
        ("/api/vocab/", True),
        ("/api/extension/lookup", True),
        ("/api/documents", False),
        ("/api/vocab/review", False),
        ("/api/reading/rearrange", False),
        ("/api/users/me", False),
    ],
)
def test_allow_list(path: str, allowed: bool) -> None:
    assert is_extension_allowed(path) is allowed


def test_extension_token_denied_outside_allow_list() -> None:
    http = TestClient(app)
    denied = http.get("/api/documents", headers=_bearer("extension"))
    assert denied.status_code == 403
    assert denied.json()["detail"]["error_code"] == "extension_token_scope_denied"


def test_web_and_legacy_tokens_are_not_scoped() -> None:
    http = TestClient(app)
    assert http.get("/api/no-such-route", headers=_bearer("web")).status_code == 404
    # Token cũ không có claim client_type = web.
    assert http.get("/api/no-such-route", headers=_bearer(None)).status_code == 404
    assert http.get("/api/no-such-route", headers=_bearer("extension")).status_code == 403


def test_garbage_bearer_falls_through_to_route() -> None:
    http = TestClient(app)
    assert http.get("/api/no-such-route", headers={"Authorization": "Bearer garbage"}).status_code == 404


def _register(client: TestClient) -> tuple[str, str]:
    email = f"ext_{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "StrongPass123", "target_level": "b1"})
    return email, "StrongPass123"


def test_extension_login_and_refresh_keep_scope_integration(client: TestClient) -> None:
    email, password = _register(client)
    tokens = client.post(
        "/api/auth/login", json={"email": email, "password": password, "client_type": "extension"}
    ).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # AUTH-007: route web ngoài allow-list bị từ chối.
    assert client.get("/api/users/me", headers=headers).status_code == 403
    # AUTH-007b: route trong allow-list chạy bình thường (không phải 403).
    assert client.get("/api/vocab", headers=headers).status_code != 403

    # Refresh không được "nâng cấp" token extension thành token web.
    refreshed = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).json()
    new_headers = {"Authorization": f"Bearer {refreshed['access_token']}"}
    assert client.get("/api/users/me", headers=new_headers).status_code == 403


def test_extension_lookup_route_integration(client: TestClient, monkeypatch) -> None:
    # EXT-002: token extension tra từ trên web bất kỳ qua /api/extension/lookup, cùng kết quả với Reading.
    import app.routers.reading as reading_router

    calls: list[tuple[str, str]] = []

    async def fake_lookup(term: str, context_sentence: str) -> dict:
        calls.append((term, context_sentence))
        return {"definition": "xin chào", "synonyms": [], "antonyms": [], "example_sentence": "Hello!"}

    monkeypatch.setattr(reading_router, "lookup_term", fake_lookup)
    email, password = _register(client)
    tokens = client.post(
        "/api/auth/login", json={"email": email, "password": password, "client_type": "extension"}
    ).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    payload = {"term": "hello", "context_sentence": "Hello world", "source_url": "https://example.com/a"}

    ext = client.post("/api/extension/lookup", headers=headers, json=payload)
    web = client.post("/api/reading/lookup", headers=headers, json=payload)
    assert ext.status_code == 200 and ext.json() == web.json()
    assert ext.json()["definition"] == "xin chào"
    assert calls == [("hello", "Hello world")] * 2
    # Không token -> 401 như các route riêng tư khác.
    assert client.post("/api/extension/lookup", json=payload).status_code == 401


def test_web_login_unaffected_integration(client: TestClient) -> None:
    email, password = _register(client)
    tokens = client.post("/api/auth/login", json={"email": email, "password": password}).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.get("/api/users/me", headers=headers).status_code == 200
