import asyncio
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.database import get_db
from app.main import app
from app.models.adaptive import UserError
from app.services import llm_service

PARAGRAPH = (
    "First, Anna wakes up at seven. Then she brushes her teeth. After that, she eats breakfast. "
    "Next, she walks to the bus stop. Finally, she arrives at school."
)


@pytest.fixture
def session_factory() -> Generator[async_sessionmaker[AsyncSession], None, None]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())


@pytest.fixture
def client(session_factory) -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def ollama_judge_offline(monkeypatch) -> None:
    # Mặc định coi Ollama tắt để các test luật (partial credit...) không phụ thuộc model thật;
    # test nào cần giám khảo thì tự monkeypatch lại judge_rearranged_order.
    async def offline(blocks: list[str], kind: str) -> bool:
        raise llm_service.AIServiceError("offline", "ollama_unreachable")

    monkeypatch.setattr(llm_service, "judge_rearranged_order", offline)


def _login(client: TestClient) -> dict:
    email = f"rearr_{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "StrongPass123", "target_level": "b1"})
    token = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _correct_order(shuffled: list[dict]) -> list[str]:
    # Ghép lại đúng thứ tự trong PARAGRAPH dựa trên chữ của từng khối.
    return [block["id"] for block in sorted(shuffled, key=lambda block: PARAGRAPH.index(block["text"]))]


def _fake_paragraph(monkeypatch) -> list[int]:
    calls: list[int] = []

    async def fake(level: str) -> str:
        calls.append(1)
        return PARAGRAPH

    monkeypatch.setattr(llm_service, "generate_rearrange_paragraph", fake)
    return calls


def test_reading_rearrange_partial_credit_and_error_logging(client: TestClient, session_factory, monkeypatch) -> None:
    _fake_paragraph(monkeypatch)
    headers = _login(client)

    created = client.post("/api/reading/rearrange", headers=headers)
    assert created.status_code == 201
    body = created.json()
    blocks = body["blocks"]
    assert len(blocks) == 5
    assert "correct_order" not in body

    order = _correct_order(blocks)
    # Đổi chỗ 2 khối cuối → đúng 3/5 vị trí (RD-032).
    submitted = order[:3] + [order[4], order[3]]
    result = client.post(
        f"/api/reading/rearrange/{body['attempt_id']}/submit", headers=headers, json={"block_order": submitted}
    )
    assert result.status_code == 200
    assert result.json()["score"] == 0.6
    assert result.json()["correct_order"] == order

    # Nộp lại cùng bài bị từ chối.
    again = client.post(
        f"/api/reading/rearrange/{body['attempt_id']}/submit", headers=headers, json={"block_order": order}
    )
    assert again.status_code == 400
    assert again.json()["detail"] == "attempt_already_submitted"

    # Sai vị trí → ghi user_errors loại reading_comprehension.
    async def rearrange_errors():
        async with session_factory() as session:
            return (
                await session.scalars(select(UserError).where(UserError.error_type == "reading_comprehension"))
            ).all()

    assert any((e.detail or {}).get("source") == "rearrange_reading" for e in asyncio.run(rearrange_errors()))


def test_reading_rearrange_reuses_error_but_not_while_still_open(client: TestClient, monkeypatch) -> None:
    calls = _fake_paragraph(monkeypatch)
    headers = _login(client)

    # Bài đầu (nguồn AI) nộp sai → tạo user_errors có corrected_text đầy đủ đoạn văn.
    first = client.post("/api/reading/rearrange", headers=headers).json()
    order = _correct_order(first["blocks"])
    client.post(
        f"/api/reading/rearrange/{first['attempt_id']}/submit",
        headers=headers,
        json={"block_order": list(reversed(order))},
    )
    assert len(calls) == 1

    # Bài thứ hai lấy nguồn từ lỗi đó (RD-029): cùng 5 câu, không gọi AI.
    second = client.post("/api/reading/rearrange", headers=headers)
    assert second.status_code == 201
    assert {b["text"] for b in second.json()["blocks"]} == {b["text"] for b in first["blocks"]}
    assert len(calls) == 1

    # Lỗi đó đang là nguồn của bài chưa nộp → bài thứ ba phải rơi xuống fallback AI (RD-034).
    assert client.post("/api/reading/rearrange", headers=headers).status_code == 201
    assert len(calls) == 2


def test_model_suggested_alternative_order_is_not_auto_accepted(client: TestClient, monkeypatch) -> None:
    async def fake_blocks(sentence, level):
        return {
            "sentence": "Yesterday she walked to school.",
            "chunks": ["Yesterday", "she walked", "to school."],
            "alternative_orders": [[1, 2, 0]],
        }

    monkeypatch.setattr(llm_service, "generate_grammar_blocks", fake_blocks)
    headers = _login(client)

    created = client.post("/api/writing/rearrange", headers=headers).json()
    # alternative_orders của model chỉ làm gợi ý cờ dạng mở, không được chấp nhận thẳng bằng luật.
    assert created["is_open_form"] is True
    by_text = {block["text"]: block["id"] for block in created["blocks"]}

    alternative = [by_text["she walked"], by_text["to school."], by_text["Yesterday"]]
    result = client.post(
        f"/api/writing/rearrange/{created['attempt_id']}/submit", headers=headers, json={"block_order": alternative}
    ).json()
    assert result["score"] < 1.0
    assert result["graded_by"] == "rules"  # Ollama tắt (fixture) nên chỉ có điểm luật


def test_rearrange_rejects_foreign_attempt_bad_order_and_wrong_branch(client: TestClient, monkeypatch) -> None:
    _fake_paragraph(monkeypatch)
    owner_headers = _login(client)
    other_headers = _login(client)
    created = client.post("/api/reading/rearrange", headers=owner_headers).json()
    ids = [block["id"] for block in created["blocks"]]

    stranger = client.post(
        f"/api/reading/rearrange/{created['attempt_id']}/submit", headers=other_headers, json={"block_order": ids}
    )
    assert stranger.status_code == 404

    bad = client.post(
        f"/api/reading/rearrange/{created['attempt_id']}/submit",
        headers=owner_headers,
        json={"block_order": ids[:-1] + [str(uuid.uuid4())]},
    )
    assert bad.status_code == 400
    assert bad.json()["detail"] == "invalid_block_order"

    # Endpoint Writing không chấm được bài Reading.
    wrong_branch = client.post(
        f"/api/writing/rearrange/{created['attempt_id']}/submit", headers=owner_headers, json={"block_order": ids}
    )
    assert wrong_branch.status_code == 404


def _open_form_attempt(client: TestClient, monkeypatch) -> tuple[dict, dict, dict]:
    async def fake_blocks(sentence, level):
        return {
            "sentence": "Yesterday she walked to school.",
            "chunks": ["Yesterday", "she walked", "to school."],
            "alternative_orders": [[1, 2, 0]],
        }

    monkeypatch.setattr(llm_service, "generate_grammar_blocks", fake_blocks)
    headers = _login(client)
    created = client.post("/api/writing/rearrange", headers=headers).json()
    by_text = {block["text"]: block["id"] for block in created["blocks"]}
    return headers, created, by_text


def test_open_form_unlisted_order_is_judged_by_ollama(client: TestClient, monkeypatch) -> None:
    headers, created, by_text = _open_form_attempt(client, monkeypatch)
    seen: list[tuple[list[str], str]] = []

    async def fake_judge(blocks: list[str], kind: str) -> bool:
        seen.append((blocks, kind))
        return True

    monkeypatch.setattr(llm_service, "judge_rearranged_order", fake_judge)
    # "to school. Yesterday she walked" không có trong alternative_orders của model sinh đề.
    unlisted = [by_text["to school."], by_text["Yesterday"], by_text["she walked"]]
    result = client.post(
        f"/api/writing/rearrange/{created['attempt_id']}/submit", headers=headers, json={"block_order": unlisted}
    ).json()
    assert result["score"] == 1.0
    assert result["graded_by"] == "ollama"
    assert "agrees" in result["explanation"]
    assert result["correct_order"] == unlisted
    # Giám khảo nhận các khối đúng theo thứ tự người học nộp.
    assert seen == [(["to school.", "Yesterday", "she walked"], "writing")]


def test_open_form_ollama_rejection_and_outage_keep_rule_based_score(client: TestClient, monkeypatch) -> None:
    headers, created, by_text = _open_form_attempt(client, monkeypatch)

    async def reject(blocks: list[str], kind: str) -> bool:
        return False

    monkeypatch.setattr(llm_service, "judge_rearranged_order", reject)
    wrong = [by_text["to school."], by_text["Yesterday"], by_text["she walked"]]
    rejected = client.post(
        f"/api/writing/rearrange/{created['attempt_id']}/submit", headers=headers, json={"block_order": wrong}
    ).json()
    assert rejected["score"] < 1.0
    assert rejected["graded_by"] == "ollama"

    # Ollama tắt → lượt nộp vẫn được chấm bằng luật, không lỗi 5xx.
    headers2, created2, by_text2 = _open_form_attempt(client, monkeypatch)

    async def outage(blocks: list[str], kind: str) -> bool:
        raise llm_service.AIServiceError("ollama down", "ollama_unreachable")

    monkeypatch.setattr(llm_service, "judge_rearranged_order", outage)
    wrong2 = [by_text2["to school."], by_text2["Yesterday"], by_text2["she walked"]]
    fallback = client.post(
        f"/api/writing/rearrange/{created2['attempt_id']}/submit", headers=headers2, json={"block_order": wrong2}
    )
    assert fallback.status_code == 200
    assert fallback.json()["graded_by"] == "rules"


def test_reading_rearrange_is_also_judged_by_ollama(client: TestClient, monkeypatch) -> None:
    _fake_paragraph(monkeypatch)
    seen: list[str] = []

    async def accept(blocks: list[str], kind: str) -> bool:
        seen.append(kind)
        return True

    monkeypatch.setattr(llm_service, "judge_rearranged_order", accept)
    headers = _login(client)
    created = client.post("/api/reading/rearrange", headers=headers).json()
    order = _correct_order(created["blocks"])
    swapped = order[:3] + [order[4], order[3]]

    result = client.post(
        f"/api/reading/rearrange/{created['attempt_id']}/submit", headers=headers, json={"block_order": swapped}
    ).json()
    assert seen == ["reading"]
    assert result["score"] == 1.0
    assert result["graded_by"] == "ollama"
    assert result["correct_order"] == swapped


def test_perfect_order_never_calls_ollama(client: TestClient, monkeypatch) -> None:
    _fake_paragraph(monkeypatch)

    async def must_not_call(blocks: list[str], kind: str) -> bool:
        raise AssertionError("đúng tuyệt đối thì không cần giám khảo")

    monkeypatch.setattr(llm_service, "judge_rearranged_order", must_not_call)
    headers = _login(client)
    created = client.post("/api/reading/rearrange", headers=headers).json()
    result = client.post(
        f"/api/reading/rearrange/{created['attempt_id']}/submit",
        headers=headers,
        json={"block_order": _correct_order(created["blocks"])},
    ).json()
    assert result["score"] == 1.0
    assert result["graded_by"] == "rules"


@pytest.mark.parametrize(
    ("code", "http_status", "retryable"),
    [
        ("ollama_unreachable", 503, True),
        ("ollama_model_missing", 503, False),
        ("ollama_timeout", 504, True),
        ("ai_quota_exceeded", 429, False),
        ("ai_bad_output", 502, True),
    ],
)
def test_generation_failure_returns_specific_error_body(
    client: TestClient, monkeypatch, code: str, http_status: int, retryable: bool
) -> None:
    async def broken(level: str) -> str:
        raise llm_service.AIServiceError("boom", code)

    monkeypatch.setattr(llm_service, "generate_rearrange_paragraph", broken)
    response = client.post("/api/reading/rearrange", headers=_login(client))
    assert response.status_code == http_status
    detail = response.json()["detail"]
    assert detail["code"] == code
    assert detail["retryable"] is retryable
    assert detail["message"]


def test_bad_model_output_is_retried_before_failing(client: TestClient, monkeypatch) -> None:
    calls: list[int] = []

    async def flaky(level: str) -> str:
        calls.append(1)
        return "Only one sentence." if len(calls) < 3 else PARAGRAPH

    monkeypatch.setattr(llm_service, "generate_rearrange_paragraph", flaky)
    response = client.post("/api/reading/rearrange", headers=_login(client))
    assert response.status_code == 201
    assert len(calls) == 3
