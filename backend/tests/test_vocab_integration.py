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
def vocab_client() -> Generator[TestClient, None, None]:
    # Integration test dùng PostgreSQL Docker để kiểm tra cả SQLAlchemy và constraint DB.
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Thay dependency DB của FastAPI bằng session factory riêng cho test.
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client
    finally:
        # Xóa override và đóng engine sau mỗi test.
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())


def login(client: TestClient) -> dict[str, str]:
    # Mỗi test dùng tài khoản riêng để không phụ thuộc dữ liệu cũ trong DB.
    email = f"vocab_{uuid.uuid4().hex[:12]}@example.com"
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


def test_vocab_source_rule_due_and_sm2_review(vocab_client: TestClient) -> None:
    # Lưu từ từ nguồn URL bên ngoài, phù hợp Extension flow.
    headers = login(vocab_client)
    created = vocab_client.post(
        "/api/vocab",
        headers=headers,
        json={
            "term": "ubiquitous",
            "definition": "present everywhere",
            "source_url": "https://example.com/article",
            "synonyms": ["widespread"],
        },
    )
    assert created.status_code == 201
    item = created.json()
    assert item["source_url"] == "https://example.com/article"

    # Review mới có next_review_at hiện tại nên xuất hiện trong due queue.
    due = vocab_client.get("/api/vocab/due", headers=headers)
    assert due.status_code == 200
    assert any(value["id"] == item["id"] for value in due.json())

    # Quality 5 lần đầu theo SM-2: repetition=1, interval=1 và ease factor tăng.
    first_review = vocab_client.post(
        f"/api/vocab/{item['id']}/review",
        headers=headers,
        json={"quality": 5},
    )
    assert first_review.status_code == 200
    assert first_review.json()["ease_factor"] == pytest.approx(2.6)

    # Sau review, lịch tiếp theo nằm trong tương lai nên không còn due ngay.
    due_after_review = vocab_client.get("/api/vocab/due", headers=headers)
    assert due_after_review.status_code == 200
    assert all(value["id"] != item["id"] for value in due_after_review.json())


def test_vocab_requires_exactly_one_source(vocab_client: TestClient) -> None:
    # Không có document_id và source_url thì Pydantic chặn trước khi chạm DB.
    headers = login(vocab_client)
    missing_source = vocab_client.post(
        "/api/vocab",
        headers=headers,
        json={"term": "missing-source", "definition": "invalid"},
    )
    assert missing_source.status_code == 422

    # Cả hai nguồn cùng có cũng bị chặn, đúng business rule trong feature-reading.md.
    both_sources = vocab_client.post(
        "/api/vocab",
        headers=headers,
        json={
            "term": "two-sources",
            "document_id": str(uuid.uuid4()),
            "source_url": "https://example.com",
        },
    )
    assert both_sources.status_code == 422


def test_vocab_low_quality_review_resets_sm2_cycle(vocab_client: TestClient) -> None:
    # Từ mới, review quality=5 trước để rời khỏi trạng thái ban đầu (repetitions=0).
    headers = login(vocab_client)
    created = vocab_client.post(
        "/api/vocab",
        headers=headers,
        json={
            "term": "resilient",
            "definition": "able to recover quickly",
            "source_url": "https://example.com/resilient",
        },
    )
    item_id = created.json()["id"]

    good_review = vocab_client.post(
        f"/api/vocab/{item_id}/review",
        headers=headers,
        json={"quality": 5},
    )
    assert good_review.status_code == 200
    ease_after_good = good_review.json()["ease_factor"]
    assert ease_after_good == pytest.approx(2.6)

    # Quality=1 (quên) phải reset chu kỳ về interval=1 ngày và giảm ease factor thật trong DB,
    # không chỉ trong response — verify bằng cách gọi lại /due sau khi thời gian chưa trôi qua.
    bad_review = vocab_client.post(
        f"/api/vocab/{item_id}/review",
        headers=headers,
        json={"quality": 1},
    )
    assert bad_review.status_code == 200
    assert bad_review.json()["ease_factor"] < ease_after_good
    assert bad_review.json()["ease_factor"] == pytest.approx(2.06)

    # interval reset về 1 ngày nên next_review_at nằm trong tương lai, không due ngay.
    due_after_forget = vocab_client.get("/api/vocab/due", headers=headers)
    assert due_after_forget.status_code == 200
    assert all(value["id"] != item_id for value in due_after_forget.json())


def test_review_vocab_from_another_user_returns_not_found(vocab_client: TestClient) -> None:
    # User A tạo từ vựng của riêng mình.
    owner_headers = login(vocab_client)
    created = vocab_client.post(
        "/api/vocab",
        headers=owner_headers,
        json={
            "term": "private-word",
            "definition": "only owner can review",
            "source_url": "https://example.com/private",
        },
    )
    item_id = created.json()["id"]

    # User B không sở hữu từ này nên review phải bị từ chối bằng 404, không lộ resource.
    other_headers = login(vocab_client)
    forbidden_review = vocab_client.post(
        f"/api/vocab/{item_id}/review",
        headers=other_headers,
        json={"quality": 5},
    )
    assert forbidden_review.status_code == 404
    assert forbidden_review.json()["detail"] == "resource_not_found"


def test_vocab_duplicate_term_returns_409_case_insensitive(vocab_client: TestClient) -> None:
    headers = login(vocab_client)
    payload = {"term": "Ephemeral", "definition": "short-lived", "source_url": "https://example.com/e"}
    assert vocab_client.post("/api/vocab", headers=headers, json=payload).status_code == 201

    duplicate = vocab_client.post("/api/vocab", headers=headers, json={**payload, "term": " ephemeral "})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "vocab_duplicate"

    # User khác vẫn lưu được cùng từ.
    other = login(vocab_client)
    assert vocab_client.post("/api/vocab", headers=other, json=payload).status_code == 201


def test_vocab_from_errors_imports_dictation_words_once(vocab_client: TestClient, monkeypatch) -> None:
    from app.database import get_db as db_dependency
    from app.services import adaptive_service, reading_service

    async def fake_lookup(term: str, context: str) -> dict:
        return {"definition": f"nghia {term}", "ipa": None, "example_sentence": "", "synonyms": [], "antonyms": []}

    monkeypatch.setattr(reading_service, "lookup_term", fake_lookup)
    headers = login(vocab_client)
    user_id = uuid.UUID(vocab_client.get("/api/users/me", headers=headers).json()["id"])

    async def seed() -> None:
        async for db in app.dependency_overrides[db_dependency]():
            for word in ("ephemeral", "Ephemeral", "tenacious"):
                adaptive_service.record_error(db, user_id, "vocabulary", {"source": "dictation", "original_text": word})
            # Lỗi nguồn khác (Writing) không được biến thành thẻ từ.
            adaptive_service.record_error(db, user_id, "vocabulary", {"source": "writing", "original_text": "ignored"})
            await db.commit()

    asyncio.run(seed())

    first = vocab_client.post("/api/vocab/from-errors", headers=headers)
    assert first.status_code == 200
    assert sorted(item["term"] for item in first.json()) == ["ephemeral", "tenacious"]
    # Gọi lại: từ đã có thẻ thì không tạo trùng.
    assert vocab_client.post("/api/vocab/from-errors", headers=headers).json() == []
    # Thẻ mới vào lịch SM-2 và đến hạn ôn ngay.
    assert len(vocab_client.get("/api/vocab/due", headers=headers).json()) == 2


def test_check_sentence_validates_term_records_grammar_error_and_scopes_owner(
    vocab_client: TestClient, monkeypatch
) -> None:
    from app.services import llm_service

    calls: list[str] = []

    async def fake_judge(term: str, sentence: str) -> dict:
        calls.append(sentence)
        return {
            "meaning_fits": True,
            "grammar_ok": "go" not in sentence,
            "corrected_sentence": "She went to a tenacious fight.",
            "feedback_vi": "Sai thì của động từ.",
        }

    monkeypatch.setattr(llm_service, "judge_vocab_sentence", fake_judge)
    headers = login(vocab_client)
    item_id = vocab_client.post(
        "/api/vocab", headers=headers, json={"term": "tenacious", "definition": "kiên trì", "source_url": "https://e.com"}
    ).json()["id"]
    url = f"/api/vocab/{item_id}/check-sentence"

    # Câu không chứa từ: 422 và không tốn lượt gọi LLM.
    missing = vocab_client.post(url, headers=headers, json={"sentence": "She is very brave."})
    assert missing.status_code == 422 and missing.json()["detail"] == "term_not_used"
    assert calls == []

    # Biến thể từ ("tenaciously") vẫn tính là có dùng từ; câu đúng thì không ghi lỗi.
    good = vocab_client.post(url, headers=headers, json={"sentence": "She fought tenaciously."})
    assert good.status_code == 200 and good.json()["grammar_ok"] is True
    assert vocab_client.get("/api/adaptive/errors", headers=headers).json() == []

    # Câu sai ngữ pháp: trả đáp án sửa và ghi 1 lỗi grammar có nguồn vocab_sentence.
    bad = vocab_client.post(url, headers=headers, json={"sentence": "She go to a tenacious fight."})
    assert bad.json()["grammar_ok"] is False
    errors = vocab_client.get("/api/adaptive/errors", headers=headers).json()
    assert [e["error_type"] for e in errors] == ["grammar"]
    assert errors[0]["detail"]["source"] == "vocab_sentence"

    # User khác không chấm được từ của người này.
    other = login(vocab_client)
    assert vocab_client.post(url, headers=other, json={"sentence": "A tenacious cat."}).status_code == 404


def test_word_family_returns_forms_and_scopes_owner(vocab_client: TestClient, monkeypatch) -> None:
    from app.services import llm_service

    monkeypatch.setattr(llm_service, "_judge_json", lambda prompt, schema: {
        "word_family": [
            {"word": "decide", "part_of_speech": "Verb"},
            {"word": "Decision", "part_of_speech": "noun"},
            {"word": "decision", "part_of_speech": "noun"},
            {"word": "deciding", "part_of_speech": "present participle"},
        ],
        "collocations": ["make a decision", "make a decision", " "],
    })
    headers = login(vocab_client)
    item_id = vocab_client.post(
        "/api/vocab", headers=headers, json={"term": "decide", "definition": "quyết định", "source_url": "https://e.com"}
    ).json()["id"]
    url = f"/api/vocab/{item_id}/word-family"

    body = vocab_client.get(url, headers=headers).json()
    # Trùng (không phân biệt hoa/thường) bị gộp, loại cụm rỗng, part_of_speech chuẩn hoá về chữ thường.
    assert body["word_family"] == [
        {"word": "decide", "part_of_speech": "verb"},
        {"word": "Decision", "part_of_speech": "noun"},
        {"word": "deciding", "part_of_speech": "verb"},  # "present participle" gộp về verb
    ]
    assert body["collocations"] == ["make a decision"]
    assert vocab_client.get(url, headers=login(vocab_client)).status_code == 404
