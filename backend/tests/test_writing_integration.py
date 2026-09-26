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

# Các test dưới đây gọi Gemini thật (không mock) nên cần GOOGLE_API_KEY hợp lệ trong
# backend/.env — đúng tinh thần "test end-to-end với DB/LLM thật" của phase này.

DOCUMENT_CONTENT = (
    "Climate change is one of the most pressing challenges of the twenty-first century. "
    "Rising global temperatures are causing more frequent extreme weather events, sea level "
    "rise, and disruption to ecosystems worldwide. Scientists agree that reducing greenhouse "
    "gas emissions through renewable energy adoption is essential to limit further warming."
)

VALID_SUMMARY_TEXT = (
    "The document explains that climate change is a major challenge today because rising "
    "temperatures cause extreme weather, sea level rise, and damage to ecosystems. Scientists "
    "believe that switching to renewable energy and cutting emissions is necessary to slow "
    "down further global warming in the future."
)

VALID_ESSAY_TEXT = (
    "In my opinion, individual actions do make a meaningful difference in fighting climate "
    "change, even though large-scale industrial change is also required. When people reduce "
    "energy consumption, choose public transport, and support sustainable products, they create "
    "demand that pushes companies and governments toward greener policies. While one person "
    "alone cannot solve climate change, millions of small choices combined can accelerate the "
    "transition to a more sustainable world."
)


@pytest.fixture
def writing_client() -> Generator[TestClient, None, None]:
    # Dùng PostgreSQL Docker thật; llm_service gọi Gemini thật (không override/mock).
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
    email = f"writing_{uuid.uuid4().hex[:12]}@example.com"
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


async def _mark_ready_and_seed_chunk(document_id: str, user_id: str) -> None:
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
                content=DOCUMENT_CONTENT,
                page_or_line_ref="line-1",
            )
        )
        await session.commit()
    await engine.dispose()


def _upload_ready_document(client: TestClient, headers: dict[str, str]) -> str:
    uploaded = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("climate.docx", b"climate change source", "application/octet-stream")},
    )
    assert uploaded.status_code == 201
    document_id = uploaded.json()["id"]
    user = client.get("/api/users/me", headers=headers).json()
    asyncio.run(_mark_ready_and_seed_chunk(document_id, user["id"]))
    return document_id


def test_document_summary_full_flow_persists_real_grading(writing_client: TestClient) -> None:
    # document_summary: prompt_text cố định theo template, chấm theo coverage (rubric_scores=None).
    headers = login(writing_client)
    document_id = _upload_ready_document(writing_client, headers)

    created = writing_client.post(
        "/api/writing/submissions",
        headers=headers,
        json={"source_type": "document_summary", "document_id": document_id},
    )
    assert created.status_code == 201
    submission_id = created.json()["submission_id"]
    assert created.json()["prompt_text"]

    submitted = writing_client.post(
        f"/api/writing/submissions/{submission_id}/submit",
        headers=headers,
        json={"submitted_text": VALID_SUMMARY_TEXT},
    )
    assert submitted.status_code == 200
    body = submitted.json()
    assert 0 <= body["score"] <= 100
    assert body["cefr_level"]
    assert body["ielts_band"]
    assert body["source_type"] == "document_summary"
    # Coverage grading không dùng rubric 4 tiêu chí (đúng business rule mục 1.2 feature-writing.md).
    assert body["rubric_scores"] is None

    # GET detail phải phản ánh đúng dữ liệu đã persist thật vào Postgres.
    detail = writing_client.get(f"/api/writing/submissions/{submission_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["completed_at"] is not None
    assert detail.json()["submitted_text"] == VALID_SUMMARY_TEXT

    # Submit lần hai (idempotent) không gọi lại LLM, trả đúng kết quả đã lưu.
    resubmitted = writing_client.post(
        f"/api/writing/submissions/{submission_id}/submit",
        headers=headers,
        json={"submitted_text": "a different short text that should be ignored"},
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json() == body


def test_extended_topic_generates_related_prompt_and_grades_with_rubric(
    writing_client: TestClient,
) -> None:
    # extended_topic: backend tự sinh đề liên quan chủ đề tài liệu qua Gemini thật.
    headers = login(writing_client)
    document_id = _upload_ready_document(writing_client, headers)

    created = writing_client.post(
        "/api/writing/submissions",
        headers=headers,
        json={"source_type": "extended_topic", "document_id": document_id},
    )
    assert created.status_code == 201
    generated_prompt = created.json()["prompt_text"]
    # Đề sinh ra không được là chính văn bản tài liệu gốc (không phải yêu cầu tóm tắt).
    assert generated_prompt
    assert generated_prompt.strip() != DOCUMENT_CONTENT

    submission_id = created.json()["submission_id"]
    submitted = writing_client.post(
        f"/api/writing/submissions/{submission_id}/submit",
        headers=headers,
        json={"submitted_text": VALID_ESSAY_TEXT},
    )
    assert submitted.status_code == 200
    body = submitted.json()
    assert body["rubric_scores"] is not None
    rubric = body["rubric_scores"]
    for key in ["task_response", "coherence_cohesion", "lexical_resource", "grammatical_range_accuracy"]:
        assert 0 <= rubric[key] <= 100
    assert len(body["insights"]) >= 0  # insights có thể rỗng nhưng field phải tồn tại và là list


def test_free_topic_uses_client_prompt_directly(writing_client: TestClient) -> None:
    # free_topic không gọi LLM sinh đề — dùng thẳng prompt_text người học tự nhập.
    headers = login(writing_client)
    custom_prompt = "Do you think remote work is better than working in an office? Discuss."

    created = writing_client.post(
        "/api/writing/submissions",
        headers=headers,
        json={"source_type": "free_topic", "prompt_text": custom_prompt},
    )
    assert created.status_code == 201
    assert created.json()["prompt_text"] == custom_prompt

    submission_id = created.json()["submission_id"]
    submitted = writing_client.post(
        f"/api/writing/submissions/{submission_id}/submit",
        headers=headers,
        json={"submitted_text": VALID_ESSAY_TEXT},
    )
    assert submitted.status_code == 200
    assert submitted.json()["rubric_scores"] is not None


def test_create_submission_validation_rules(writing_client: TestClient) -> None:
    headers = login(writing_client)

    # document_summary thiếu document_id bị chặn ở schema layer, không chạm DB.
    missing_document = writing_client.post(
        "/api/writing/submissions",
        headers=headers,
        json={"source_type": "document_summary"},
    )
    assert missing_document.status_code == 422

    # free_topic kèm document_id là kết hợp không hợp lệ theo business rule.
    invalid_combo = writing_client.post(
        "/api/writing/submissions",
        headers=headers,
        json={
            "source_type": "free_topic",
            "document_id": str(uuid.uuid4()),
            "prompt_text": "Some topic",
        },
    )
    assert invalid_combo.status_code == 422

    # free_topic thiếu prompt_text cũng bị chặn.
    missing_prompt = writing_client.post(
        "/api/writing/submissions",
        headers=headers,
        json={"source_type": "free_topic"},
    )
    assert missing_prompt.status_code == 422


def test_submit_rejects_essay_under_minimum_word_count(writing_client: TestClient) -> None:
    # Bài dưới 30 từ phải bị từ chối nghiệp vụ, không tạo dữ liệu chấm rác/không gọi LLM.
    headers = login(writing_client)
    created = writing_client.post(
        "/api/writing/submissions",
        headers=headers,
        json={"source_type": "free_topic", "prompt_text": "Describe your favorite hobby."},
    )
    submission_id = created.json()["submission_id"]

    too_short = writing_client.post(
        f"/api/writing/submissions/{submission_id}/submit",
        headers=headers,
        json={"submitted_text": "I like reading books."},
    )
    assert too_short.status_code == 400
    assert too_short.json()["detail"] == "submission_too_short"


def test_submission_from_another_user_returns_not_found(writing_client: TestClient) -> None:
    owner_headers = login(writing_client)
    created = writing_client.post(
        "/api/writing/submissions",
        headers=owner_headers,
        json={"source_type": "free_topic", "prompt_text": "A private topic only I should see."},
    )
    submission_id = created.json()["submission_id"]

    other_headers = login(writing_client)
    hidden = writing_client.get(f"/api/writing/submissions/{submission_id}", headers=other_headers)
    assert hidden.status_code == 404
    assert hidden.json()["detail"] == "submission_not_found"


# ==================== POST /api/writing/prompts/suggest ====================


def test_prompts_suggest_document_summary_returns_fixed_template(writing_client: TestClient) -> None:
    headers = login(writing_client)
    document_id = _upload_ready_document(writing_client, headers)

    response = writing_client.post(
        "/api/writing/prompts/suggest",
        headers=headers,
        json={"source_type": "document_summary", "document_id": document_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_type"] == "document_summary"
    assert body["prompt_text"]
    assert body["prompt_options"] is None


def test_prompts_suggest_extended_topic_calls_gemini(writing_client: TestClient) -> None:
    # extended_topic sinh đề thật qua Gemini, không được trùng nội dung tài liệu gốc.
    headers = login(writing_client)
    document_id = _upload_ready_document(writing_client, headers)

    response = writing_client.post(
        "/api/writing/prompts/suggest",
        headers=headers,
        json={"source_type": "extended_topic", "document_id": document_id, "level": "b2"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_type"] == "extended_topic"
    assert body["prompt_text"]
    assert body["prompt_text"].strip() != DOCUMENT_CONTENT


def test_prompts_suggest_free_topic_with_topic_returns_as_is(writing_client: TestClient) -> None:
    headers = login(writing_client)
    response = writing_client.post(
        "/api/writing/prompts/suggest",
        headers=headers,
        json={"source_type": "free_topic", "topic": "Should schools ban smartphones?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["prompt_text"] == "Should schools ban smartphones?"
    assert body["prompt_options"] is None


def test_prompts_suggest_free_topic_certificate_style_returns_multiple_options(
    writing_client: TestClient,
) -> None:
    # certificate_style (không kèm topic) → nhiều lựa chọn thật từ Gemini, CHƯA tạo submission.
    headers = login(writing_client)
    response = writing_client.post(
        "/api/writing/prompts/suggest",
        headers=headers,
        json={"source_type": "free_topic", "certificate_style": "ielts", "level": "b2"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["prompt_text"] is None
    assert body["prompt_options"] is not None
    assert len(body["prompt_options"]) >= 2
    for option in body["prompt_options"]:
        assert isinstance(option, str) and option.strip()


def test_prompts_suggest_validation_rules(writing_client: TestClient) -> None:
    headers = login(writing_client)

    missing_document = writing_client.post(
        "/api/writing/prompts/suggest",
        headers=headers,
        json={"source_type": "extended_topic"},
    )
    assert missing_document.status_code == 422

    both_topic_and_style = writing_client.post(
        "/api/writing/prompts/suggest",
        headers=headers,
        json={"source_type": "free_topic", "topic": "AI", "certificate_style": "ielts"},
    )
    assert both_topic_and_style.status_code == 422

    neither = writing_client.post(
        "/api/writing/prompts/suggest",
        headers=headers,
        json={"source_type": "free_topic"},
    )
    assert neither.status_code == 422


# ==================== POST /api/writing/grammar-check ====================

TEXT_WITH_GRAMMAR_ERRORS = "She go to school every day and dont like homework at all."


def test_grammar_check_raw_text_preview_does_not_persist(writing_client: TestClient) -> None:
    headers = login(writing_client)
    response = writing_client.post(
        "/api/writing/grammar-check",
        headers=headers,
        json={"raw_text": TEXT_WITH_GRAMMAR_ERRORS},
    )
    assert response.status_code == 200
    insights = response.json()["insights"]
    assert len(insights) >= 1
    for insight in insights:
        assert insight["insight_type"] == "grammar"
        assert 0 <= insight["offset_start"] < insight["offset_end"] <= len(TEXT_WITH_GRAMMAR_ERRORS)
        assert insight["explanation"]


def test_grammar_check_submission_id_persists_writing_insights(writing_client: TestClient) -> None:
    headers = login(writing_client)
    created = writing_client.post(
        "/api/writing/submissions",
        headers=headers,
        json={"source_type": "free_topic", "prompt_text": "Describe your daily routine."},
    )
    submission_id = created.json()["submission_id"]
    # Nộp bài thật (đủ 30 từ) chứa lỗi ngữ pháp rõ ràng để grammar-check có gì để phát hiện.
    long_text_with_errors = (
        TEXT_WITH_GRAMMAR_ERRORS
        + " I usually wake up early, have breakfast, and then goes to work by bus every single"
        + " morning without any delay, even when the weather outside are quite bad and cold."
    )
    submit = writing_client.post(
        f"/api/writing/submissions/{submission_id}/submit",
        headers=headers,
        json={"submitted_text": long_text_with_errors},
    )
    assert submit.status_code == 200

    response = writing_client.post(
        "/api/writing/grammar-check",
        headers=headers,
        json={"submission_id": submission_id},
    )
    assert response.status_code == 200
    assert len(response.json()["insights"]) >= 1

    # Xác nhận đã lưu THẬT vào writing_insights (không chỉ trả về trong response).
    async def count_grammar_insights() -> int:
        settings = get_settings()
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            from sqlalchemy import select

            from app.models.writing import WritingInsight

            result = await session.execute(
                select(WritingInsight).where(
                    WritingInsight.writing_submission_id == uuid.UUID(submission_id),
                    WritingInsight.insight_type == "grammar",
                )
            )
            rows = list(result.scalars().all())
        await engine.dispose()
        return len(rows)

    assert asyncio.run(count_grammar_insights()) >= 1


def test_grammar_check_requires_exactly_one_source(writing_client: TestClient) -> None:
    headers = login(writing_client)

    neither = writing_client.post("/api/writing/grammar-check", headers=headers, json={})
    assert neither.status_code == 422

    both = writing_client.post(
        "/api/writing/grammar-check",
        headers=headers,
        json={"submission_id": str(uuid.uuid4()), "raw_text": "Some text"},
    )
    assert both.status_code == 422


# ==================== POST /api/writing/rephrase ====================


def test_rephrase_explicit_sentence_returns_alternatives(writing_client: TestClient) -> None:
    headers = login(writing_client)
    created = writing_client.post(
        "/api/writing/submissions",
        headers=headers,
        json={"source_type": "free_topic", "prompt_text": "Describe your favorite season."},
    )
    submission_id = created.json()["submission_id"]
    writing_client.post(
        f"/api/writing/submissions/{submission_id}/submit",
        headers=headers,
        json={"submitted_text": VALID_ESSAY_TEXT},
    )

    target_sentence = "While one person alone cannot solve climate change, millions of small choices combined can accelerate the transition to a more sustainable world."
    response = writing_client.post(
        "/api/writing/rephrase",
        headers=headers,
        json={"submission_id": submission_id, "sentence_text": target_sentence},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["original_sentence"]
    assert len(body["suggested_sentences"]) >= 1
    for suggestion in body["suggested_sentences"]:
        assert suggestion["text"]
        assert suggestion["explanation"]


def test_rephrase_without_sentence_picks_weakest_automatically(writing_client: TestClient) -> None:
    headers = login(writing_client)
    created = writing_client.post(
        "/api/writing/submissions",
        headers=headers,
        json={"source_type": "free_topic", "prompt_text": "Describe your favorite season."},
    )
    submission_id = created.json()["submission_id"]
    writing_client.post(
        f"/api/writing/submissions/{submission_id}/submit",
        headers=headers,
        json={"submitted_text": VALID_ESSAY_TEXT},
    )

    response = writing_client.post(
        "/api/writing/rephrase",
        headers=headers,
        json={"submission_id": submission_id},
    )
    assert response.status_code == 200
    assert response.json()["original_sentence"]
    assert len(response.json()["suggested_sentences"]) >= 1


def test_rephrase_requires_submitted_essay(writing_client: TestClient) -> None:
    headers = login(writing_client)
    created = writing_client.post(
        "/api/writing/submissions",
        headers=headers,
        json={"source_type": "free_topic", "prompt_text": "Not submitted yet."},
    )
    submission_id = created.json()["submission_id"]

    response = writing_client.post(
        "/api/writing/rephrase",
        headers=headers,
        json={"submission_id": submission_id},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "submission_not_submitted_yet"


def test_rephrase_from_another_user_returns_not_found(writing_client: TestClient) -> None:
    owner_headers = login(writing_client)
    created = writing_client.post(
        "/api/writing/submissions",
        headers=owner_headers,
        json={"source_type": "free_topic", "prompt_text": "Private essay."},
    )
    submission_id = created.json()["submission_id"]
    writing_client.post(
        f"/api/writing/submissions/{submission_id}/submit",
        headers=owner_headers,
        json={"submitted_text": VALID_ESSAY_TEXT},
    )

    other_headers = login(writing_client)
    response = writing_client.post(
        "/api/writing/rephrase",
        headers=other_headers,
        json={"submission_id": submission_id},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "submission_not_found"
