import asyncio
import io
import uuid
from collections.abc import Generator

import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.database import get_db
from app.main import app

DOCUMENT_TEXT = (
    "Coral reefs support around twenty five percent of all marine species despite covering "
    "less than one percent of the ocean floor. Rising sea temperatures cause coral bleaching, "
    "a process where corals expel the algae living in their tissues, turning white and "
    "becoming vulnerable to disease. Scientists are working on heat-resistant coral strains "
    "to help reefs survive a warming climate."
)


def make_docx_bytes(text: str) -> bytes:
    document = DocxDocument()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def skim_client() -> Generator[TestClient, None, None]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())


def login(client: TestClient) -> dict[str, str]:
    email = f"skim_{uuid.uuid4().hex[:12]}@example.com"
    assert client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPass123", "target_level": "b1"},
    ).status_code == 201
    response = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_skim_scan_from_document_uses_real_excerpt_not_ai_text(skim_client: TestClient) -> None:
    # document_id set → passage phải là excerpt THẬT của tài liệu, không phải văn bản AI bịa.
    headers = login(skim_client)
    uploaded = skim_client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("coral.docx", make_docx_bytes(DOCUMENT_TEXT), "application/octet-stream")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["status"] == "ready"
    document_id = uploaded.json()["id"]

    created = skim_client.post(
        "/api/reading/skim-scan/sessions",
        headers=headers,
        json={"level": "b1", "document_id": document_id},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["source_document_id"] == document_id
    # Passage phải trùng khớp nguyên văn với nội dung tài liệu đã upload (không AI paraphrase).
    assert body["content"].strip() == DOCUMENT_TEXT.strip()
    # Câu hỏi vẫn do AI sinh, bám nội dung thật.
    assert len(body["questions"]) >= 1
    for question in body["questions"]:
        assert len(question["options"]) == 4

    # Submit thử để xác nhận session dùng chung hạ tầng chấm điểm với Classic Mode.
    session_id = body["session_id"]
    first_question_id = body["questions"][0]["id"]
    submitted = skim_client.post(
        f"/api/reading/sessions/{session_id}/submit",
        headers=headers,
        json={"answers": [{"question_id": first_question_id, "selected_option_index": 0}]},
    )
    assert submitted.status_code == 200
    assert 0 <= submitted.json()["score"] <= 1


def test_skim_scan_from_topic_generates_ai_passage(skim_client: TestClient) -> None:
    # topic set (không document_id) → passage do Gemini tự sinh, không gắn tài liệu nào.
    headers = login(skim_client)
    created = skim_client.post(
        "/api/reading/skim-scan/sessions",
        headers=headers,
        json={"level": "b1", "topic": "renewable energy"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["source_document_id"] is None
    assert len(body["content"].split()) > 30
    assert len(body["questions"]) >= 1


def test_skim_scan_rejects_both_or_neither_source(skim_client: TestClient) -> None:
    headers = login(skim_client)

    neither = skim_client.post(
        "/api/reading/skim-scan/sessions",
        headers=headers,
        json={"level": "b1"},
    )
    assert neither.status_code == 422

    both = skim_client.post(
        "/api/reading/skim-scan/sessions",
        headers=headers,
        json={"level": "b1", "topic": "space travel", "document_id": str(uuid.uuid4())},
    )
    assert both.status_code == 422


def test_skim_scan_document_not_ready_is_rejected(skim_client: TestClient) -> None:
    headers = login(skim_client)
    uploaded = skim_client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("broken.docx", b"not a real docx file", "application/octet-stream")},
    )
    assert uploaded.json()["status"] == "failed"
    document_id = uploaded.json()["id"]

    blocked = skim_client.post(
        "/api/reading/skim-scan/sessions",
        headers=headers,
        json={"level": "b1", "document_id": document_id},
    )
    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "document_not_ready"
