import asyncio
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.database import get_db
from app.main import app
from app.models.notebook import Document, DocumentChunk


@pytest.fixture
def classic_client() -> Generator[TestClient, None, None]:
    # Dùng PostgreSQL Docker thật để kiểm tra document/chunk/session/answer cùng nhau.
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Override DB dependency của FastAPI trong thời gian test.
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
    # Tạo user riêng cho test Reading.
    email = f"classic_{uuid.uuid4().hex[:12]}@example.com"
    assert client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPass123", "target_level": "b1"},
    ).status_code == 201
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def mark_document_ready_and_seed_chunk(
    document_id: str,
    user_id: str,
) -> None:
    # Seed dữ liệu tiền xử lý RAG tối thiểu để Classic Mode có citation source.
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await session.execute(
            update(Document)
            .where(Document.id == uuid.UUID(document_id), Document.user_id == uuid.UUID(user_id))
            .values(status="ready")
        )
        session.add(
            DocumentChunk(
                document_id=uuid.UUID(document_id),
                chunk_index=0,
                content="Artificial intelligence supports human decision making.",
                page_or_line_ref="line-1",
            )
        )
        await session.commit()
    await engine.dispose()


def test_classic_session_hides_answers_and_is_idempotent(
    classic_client: TestClient,
) -> None:
    # Tạo document qua API Notebook để giữ đúng ownership flow.
    headers = login(classic_client)
    user = classic_client.get("/api/users/me", headers=headers).json()
    uploaded = classic_client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("reading.docx", b"reading source", "application/octet-stream")},
    )
    assert uploaded.status_code == 201
    document_id = uploaded.json()["id"]
    asyncio.run(mark_document_ready_and_seed_chunk(document_id, user["id"]))

    # Tạo Classic session; response không được có correct_option_index.
    created = classic_client.post(
        "/api/reading/classic/sessions",
        headers=headers,
        json={"document_id": document_id, "num_questions": 3},
    )
    assert created.status_code == 201
    payload = created.json()
    assert len(payload["questions"]) == 1
    assert all("correct_option_index" not in question for question in payload["questions"])

    # Chọn đáp án đầu tiên, là đáp án đúng của deterministic fallback.
    question_id = payload["questions"][0]["id"]
    submitted = classic_client.post(
        f"/api/reading/sessions/{payload['session_id']}/submit",
        headers=headers,
        json={"answers": [{"question_id": question_id, "selected_option_index": 0}]},
    )
    assert submitted.status_code == 200
    assert submitted.json()["score"] == 1.0
    first_result = submitted.json()

    # Submit lần hai trả kết quả cũ, không tạo answer trùng.
    repeated = classic_client.post(
        f"/api/reading/sessions/{payload['session_id']}/submit",
        headers=headers,
        json={"answers": [{"question_id": question_id, "selected_option_index": 1}]},
    )
    assert repeated.status_code == 200
    assert repeated.json() == first_result


def test_submit_rejects_out_of_range_option_index(classic_client: TestClient) -> None:
    # Pydantic chặn index ngoài [0, 3] ngay ở schema layer (khớp đúng 4 lựa chọn cố định
    # của fallback question hiện tại) — request không bao giờ chạm tới DB/service.
    headers = login(classic_client)
    user = classic_client.get("/api/users/me", headers=headers).json()
    uploaded = classic_client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("reading2.docx", b"reading source 2", "application/octet-stream")},
    )
    document_id = uploaded.json()["id"]
    asyncio.run(mark_document_ready_and_seed_chunk(document_id, user["id"]))

    created = classic_client.post(
        "/api/reading/classic/sessions",
        headers=headers,
        json={"document_id": document_id, "num_questions": 3},
    )
    question_id = created.json()["questions"][0]["id"]

    invalid = classic_client.post(
        f"/api/reading/sessions/{created.json()['session_id']}/submit",
        headers=headers,
        json={"answers": [{"question_id": question_id, "selected_option_index": 99}]},
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"][0]["loc"][-1] == "selected_option_index"


def test_submit_to_nonexistent_session_returns_not_found(
    classic_client: TestClient,
) -> None:
    # Session ngẫu nhiên không tồn tại trong DB thật phải trả 404, không 500.
    headers = login(classic_client)
    missing_session_id = uuid.uuid4()
    response = classic_client.post(
        f"/api/reading/sessions/{missing_session_id}/submit",
        headers=headers,
        json={"answers": [{"question_id": str(uuid.uuid4()), "selected_option_index": 0}]},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "session_not_found"
