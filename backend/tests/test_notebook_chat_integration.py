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

# Chat dùng RAG thật (Gemini embedding + generation, pgvector cosine search trên Postgres
# thật) — không mock bất kỳ bước nào, đúng tinh thần verify end-to-end của phase này.

DOCUMENT_TEXT = (
    "The Eiffel Tower was completed in 1889 for the World's Fair in Paris, France. "
    "It was designed by engineer Gustave Eiffel and stands 330 meters tall. "
    "For many years it was the tallest man-made structure in the world.\n\n"
    "The Great Wall of China was built over many centuries by several Chinese dynasties "
    "to protect against invasions from northern nomadic groups. It stretches over "
    "21000 kilometers, making it one of the largest construction projects in human history."
)


def make_docx_bytes(text: str) -> bytes:
    document = DocxDocument()
    for paragraph in text.split("\n\n"):
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def chat_client() -> Generator[TestClient, None, None]:
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
    email = f"chat_{uuid.uuid4().hex[:12]}@example.com"
    assert client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPass123", "target_level": "b1"},
    ).status_code == 201
    response = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def upload_ready_document(client: TestClient, headers: dict[str, str]) -> str:
    uploaded = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("landmarks.docx", make_docx_bytes(DOCUMENT_TEXT), "application/octet-stream")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["status"] == "ready"
    return uploaded.json()["id"]


def test_chat_answers_grounded_in_uploaded_document(chat_client: TestClient) -> None:
    headers = login(chat_client)
    document_id = upload_ready_document(chat_client, headers)

    asked = chat_client.post(
        f"/api/documents/{document_id}/chat",
        headers=headers,
        json={"message": "Who designed the Eiffel Tower and how tall is it?"},
    )
    assert asked.status_code == 201
    body = asked.json()
    assert body["user_message"]["role"] == "user"
    assert body["assistant_message"]["role"] == "assistant"
    answer = body["assistant_message"]["content"].lower()
    # RAG thật phải trả lời đúng dựa trên nội dung tài liệu, không phải kiến thức chung chung.
    assert "eiffel" in answer or "gustave" in answer or "330" in answer
    # Phải có trích dẫn nguồn (chunk thật trong document_chunks), không rỗng.
    assert len(body["assistant_message"]["sources"]) > 0

    # Lịch sử chat phải persist thật trong DB — GET lại phải thấy đủ 2 tin nhắn.
    history = chat_client.get(f"/api/documents/{document_id}/chat", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 2
    assert history.json()[0]["role"] == "user"
    assert history.json()[1]["role"] == "assistant"


def test_chat_requires_document_ready(chat_client: TestClient) -> None:
    headers = login(chat_client)
    # Upload file .docx hỏng (không parse được) → status thật sẽ là "failed", không "ready".
    uploaded = chat_client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("broken.docx", b"not a real docx file", "application/octet-stream")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["status"] == "failed"
    document_id = uploaded.json()["id"]

    blocked = chat_client.post(
        f"/api/documents/{document_id}/chat",
        headers=headers,
        json={"message": "What is this about?"},
    )
    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "document_not_ready"


def test_chat_from_another_user_returns_not_found(chat_client: TestClient) -> None:
    owner_headers = login(chat_client)
    document_id = upload_ready_document(chat_client, owner_headers)

    other_headers = login(chat_client)
    hidden = chat_client.post(
        f"/api/documents/{document_id}/chat",
        headers=other_headers,
        json={"message": "Tell me about this document"},
    )
    assert hidden.status_code == 404
    assert hidden.json()["detail"] == "document_not_found"
