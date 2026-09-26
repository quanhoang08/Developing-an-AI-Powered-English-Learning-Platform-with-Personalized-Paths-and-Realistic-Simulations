import asyncio
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
def reading_client() -> Generator[TestClient, None, None]:
    # Dùng DB thật để kiểm tra auth dependency của Reading lookup.
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Override DB session cho TestClient.
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client
    finally:
        # Luôn dọn override/engine để không ảnh hưởng test kế tiếp.
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())


def test_reading_lookup_requires_auth_and_returns_contract(
    reading_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Không có token phải bị từ chối theo API spec.
    unauthorized = reading_client.post(
        "/api/reading/lookup",
        json={"term": "pervasive", "context_sentence": "AI is pervasive."},
    )
    assert unauthorized.status_code == 401

    # Đăng ký/đăng nhập user để gọi lookup private.
    email = f"reading_{uuid.uuid4().hex[:12]}@example.com"
    assert reading_client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPass123", "target_level": "b1"},
    ).status_code == 201
    login = reading_client.post(
        "/api/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    token = login.json()["access_token"]

    # Lookup thật gọi Ollama (chậm, không xác định) — test hợp đồng response nên thay bằng bản giả.
    async def fake_lookup_term(term: str, context_sentence: str) -> dict:
        return {
            "definition": "tràn ngập",
            "synonyms": ["widespread"],
            "antonyms": [],
            "example_sentence": context_sentence,
            "ipa": "/pəˈveɪsɪv/",
            "senses": [
                {"part_of_speech": "adjective", "level": "C1", "meaning_vi": "tràn ngập", "example_en": context_sentence}
            ],
        }

    monkeypatch.setattr("app.routers.reading.lookup_term", fake_lookup_term)
    response = reading_client.post(
        "/api/reading/lookup",
        headers={"Authorization": f"Bearer {token}"},
        json={"term": "pervasive", "context_sentence": "AI is pervasive."},
    )
    assert response.status_code == 200
    assert set(response.json()) == {
        "definition",
        "synonyms",
        "antonyms",
        "example_sentence",
        "ipa",
        "senses",
    }
    assert response.json()["senses"][0]["level"] == "C1"
