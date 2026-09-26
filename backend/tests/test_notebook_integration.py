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


def make_docx_bytes(paragraph_text: str) -> bytes:
    # Ingestion thật (rag_service) giờ parse nội dung file bằng python-docx, nên test upload
    # cần bytes .docx hợp lệ thay vì chuỗi giả — khác với trước khi có pipeline ingest.
    document = DocxDocument()
    document.add_paragraph(paragraph_text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def notebook_client() -> Generator[TestClient, None, None]:
    # Dùng PostgreSQL Docker thật để test cả ORM, constraints và upload workflow.
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Mọi request trong test dùng session factory riêng, tránh ảnh hưởng test khác.
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client
    finally:
        # Dọn dependency override và engine sau khi test kết thúc.
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())


def register_and_login(client: TestClient) -> dict[str, str]:
    # Tạo user riêng cho mỗi test để không phụ thuộc dữ liệu tồn tại trước đó.
    email = f"notebook_{uuid.uuid4().hex[:12]}@example.com"
    registered = client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPass123", "target_level": "b1"},
    )
    assert registered.status_code == 201

    logged_in = client.post(
        "/api/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert logged_in.status_code == 200
    return {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


def test_folder_upload_list_and_reject_unsupported_file(
    notebook_client: TestClient,
) -> None:
    # Folder được tạo dưới owner hiện tại.
    headers = register_and_login(notebook_client)
    folder_response = notebook_client.post(
        "/api/notebook-folders",
        headers=headers,
        json={"name": "Reading materials"},
    )
    assert folder_response.status_code == 201
    folder_id = folder_response.json()["id"]

    # DOCX hợp lệ được ingest thật ngay lúc upload (extract + chunk + embed) nên đã "ready".
    upload_response = notebook_client.post(
        "/api/documents",
        headers=headers,
        data={"folder_id": folder_id, "tags": "b1"},
        files={
            "file": (
                "lesson.docx",
                make_docx_bytes("Photosynthesis is the process plants use to convert light into energy."),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert upload_response.status_code == 201
    document = upload_response.json()
    assert document["source_type"] == "docx"
    assert document["status"] == "ready"
    assert document["folder_id"] == folder_id

    # List endpoint trả pagination wrapper và lọc đúng folder.
    listed = notebook_client.get(
        "/api/documents",
        headers=headers,
        params={"folder_id": folder_id},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == document["id"]

    # PDF không thuộc phạm vi audio/.docx nên bị từ chối trước khi lưu.
    rejected = notebook_client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("lesson.pdf", b"pdf", "application/pdf")},
    )
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "unsupported_file_type"


def test_document_from_another_user_returns_not_found(
    notebook_client: TestClient,
) -> None:
    # User A tạo document trước.
    owner_headers = register_and_login(notebook_client)
    upload_response = notebook_client.post(
        "/api/documents",
        headers=owner_headers,
        files={"file": ("private.docx", b"private", "application/octet-stream")},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    # User B không được biết resource tồn tại, nên API trả 404 thay vì 403.
    other_headers = register_and_login(notebook_client)
    hidden = notebook_client.get(f"/api/documents/{document_id}", headers=other_headers)
    assert hidden.status_code == 404
    assert hidden.json()["detail"] == "resource_not_found"


def test_update_and_delete_document_persist_in_real_db(
    notebook_client: TestClient,
) -> None:
    # Upload document gốc để có resource thật cần cập nhật/xóa.
    headers = register_and_login(notebook_client)
    uploaded = notebook_client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("notes.docx", b"notes content", "application/octet-stream")},
    )
    assert uploaded.status_code == 201
    document_id = uploaded.json()["id"]
    assert uploaded.json()["starred"] is False

    # PATCH chỉ đổi field được truyền, ghi thẳng vào DB thật (không mock).
    patched = notebook_client.patch(
        f"/api/documents/{document_id}",
        headers=headers,
        json={"starred": True, "tags": ["important", "exam"]},
    )
    assert patched.status_code == 200
    assert patched.json()["starred"] is True
    assert patched.json()["tags"] == ["important", "exam"]

    # GET lại để xác nhận thay đổi thực sự được persist, không chỉ trả về response cũ.
    refetched = notebook_client.get(f"/api/documents/{document_id}", headers=headers)
    assert refetched.status_code == 200
    assert refetched.json()["starred"] is True
    assert refetched.json()["tags"] == ["important", "exam"]

    # DELETE phải xóa thật khỏi DB — GET sau đó phải trả 404.
    deleted = notebook_client.delete(f"/api/documents/{document_id}", headers=headers)
    assert deleted.status_code == 204

    after_delete = notebook_client.get(f"/api/documents/{document_id}", headers=headers)
    assert after_delete.status_code == 404


def test_update_document_rejects_unowned_folder(notebook_client: TestClient) -> None:
    # Folder thuộc user khác không được dùng để cập nhật document của mình.
    owner_headers = register_and_login(notebook_client)
    uploaded = notebook_client.post(
        "/api/documents",
        headers=owner_headers,
        files={"file": ("solo.docx", b"solo", "application/octet-stream")},
    )
    document_id = uploaded.json()["id"]

    other_headers = register_and_login(notebook_client)
    other_folder = notebook_client.post(
        "/api/notebook-folders",
        headers=other_headers,
        json={"name": "Other user's folder"},
    )
    other_folder_id = other_folder.json()["id"]

    rejected = notebook_client.patch(
        f"/api/documents/{document_id}",
        headers=owner_headers,
        json={"folder_id": other_folder_id},
    )
    assert rejected.status_code == 404
    assert rejected.json()["detail"] == "folder_not_found"
