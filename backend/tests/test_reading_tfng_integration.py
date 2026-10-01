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
from app.services import llm_service

PASSAGE = {
    "title": "Coral",
    "content": "Coral reefs cover less than one percent of the ocean floor. " * 6,
    "target_vocab_words": [],
}
FAKE_TFNG = [
    {"statement": "Reefs cover most of the ocean.", "answer": "False", "explanation": "Passage: 'less than one percent'."},
    {"statement": "Reefs are older than fish.", "answer": "Not Given", "explanation": "Age is never mentioned."},
    {"statement": "Reefs are small in area.", "answer": "True", "explanation": "Passage: 'less than one percent'."},
    {"statement": "Bad item", "answer": "Maybe", "explanation": "dropped: not a valid answer"},
]


@pytest.fixture
def client(monkeypatch) -> Generator[TestClient, None, None]:
    async def fake_passage(topic, level):
        return PASSAGE

    async def fake_tfng(content, level, n):
        return FAKE_TFNG

    monkeypatch.setattr(llm_service, "generate_skim_scan_passage", fake_passage)
    monkeypatch.setattr(llm_service, "generate_tfng_questions", fake_tfng)

    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())


def test_tfng_session_fixed_options_hidden_answer_and_explanation_after_submit(client: TestClient) -> None:
    email = f"tfng_{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "StrongPass123", "target_level": "b1"})
    token = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/reading/skim-scan/sessions",
        headers=headers,
        json={"level": "b1", "topic": "coral", "question_type": "tfng"},
    )
    assert created.status_code == 201
    body = created.json()
    # Mục có answer không hợp lệ bị loại; 3 mục hợp lệ còn lại.
    assert len(body["questions"]) == 3
    for question in body["questions"]:
        assert question["options"] == ["True", "False", "Not Given"]
        assert "explanation" not in question and "correct_option_index" not in question

    answers = [{"question_id": q["id"], "selected_option_index": 0} for q in body["questions"]]
    submitted = client.post(f"/api/reading/sessions/{body['session_id']}/submit", headers=headers, json={"answers": answers})
    assert submitted.status_code == 200
    results = submitted.json()["results"]
    assert sorted(r["correct_option_index"] for r in results) == [0, 1, 2]
    assert all(r["explanation"] for r in results)
    assert submitted.json()["score"] == round(1 / 3, 2)


def test_default_question_type_has_no_explanation_and_rejects_unknown_type(client: TestClient) -> None:
    email = f"tfng_{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "StrongPass123", "target_level": "b1"})
    token = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"}).json()["access_token"]
    bad = client.post(
        "/api/reading/skim-scan/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"level": "b1", "topic": "coral", "question_type": "essay"},
    )
    assert bad.status_code == 422
