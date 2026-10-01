import asyncio
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.database import get_db
from app.main import app
from app.models.adaptive import UserError
from app.models.gamification import Streak
from app.services import adaptive_service, llm_service
from app.services.priority_queue_service import error_priority, vocab_priority

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


# ---------- Logic thuần (không cần DB) ----------


def test_error_priority_prefers_unreviewed_recent_and_frequent_errors() -> None:
    fresh = error_priority(0, NOW, 1, NOW)
    reviewed = error_priority(3, NOW, 1, NOW)
    old = error_priority(0, NOW - timedelta(days=30), 1, NOW)
    frequent = error_priority(0, NOW, 6, NOW)
    assert fresh > reviewed
    assert fresh > old
    assert frequent > fresh
    # Lỗi đã ôn đúng không còn được cộng điểm "mới xảy ra".
    assert error_priority(1, NOW, 1, NOW) == error_priority(1, NOW - timedelta(days=30), 1, NOW)


def test_vocab_priority_grows_with_overdue_days_and_hard_cards() -> None:
    assert vocab_priority(10, 2.5) > vocab_priority(1, 2.5)
    assert vocab_priority(1, 1.3) > vocab_priority(1, 2.5)
    # Trễ hạn được chặn ở 30 ngày để một từ bỏ quên lâu không lấn át mọi thứ khác.
    assert vocab_priority(300, 2.5) == vocab_priority(30, 2.5)


def test_validate_questions_drops_malformed_llm_output() -> None:
    sources = [{"id": uuid.uuid4(), "error_type": "grammar"}]
    good = {"source_index": 0, "question_text": "q", "options": ["a", "b", "c", "d"], "correct_option_index": 2, "explanation": "e"}
    bad_answer = {**good, "correct_option_index": 9}
    bad_source = {**good, "source_index": 5}
    too_few_options = {**good, "options": ["a"], "correct_option_index": 0}
    questions = adaptive_service.validate_questions([good, bad_answer, bad_source, too_few_options], sources)
    assert len(questions) == 1
    assert questions[0]["error_id"] == str(sources[0]["id"])
    assert questions[0]["error_type"] == "grammar"


def test_shuffle_options_keeps_the_correct_answer_pointing_at_the_same_text() -> None:
    questions = [
        {"options": ["a", "b", "c", "d"], "correct_option_index": 1},
        {"options": ["w", "x", "y", "z"], "correct_option_index": 3},
    ]
    seen_positions = set()
    for _ in range(200):
        shuffled = [{"options": list(q["options"]), "correct_option_index": q["correct_option_index"]} for q in questions]
        adaptive_service.shuffle_options(shuffled)
        assert shuffled[0]["options"][shuffled[0]["correct_option_index"]] == "b"
        assert shuffled[1]["options"][shuffled[1]["correct_option_index"]] == "z"
        assert sorted(shuffled[0]["options"]) == ["a", "b", "c", "d"]
        seen_positions.add(shuffled[0]["correct_option_index"])
    assert seen_positions == {0, 1, 2, 3}


def test_public_questions_hide_answers() -> None:
    public = adaptive_service.public_questions(
        [{"question_text": "q", "options": ["a", "b"], "correct_option_index": 1, "explanation": "x", "error_id": "1", "error_type": "grammar"}]
    )
    assert public == [{"question_text": "q", "options": ["a", "b"], "error_type": "grammar"}]


def test_summarize_habits_with_no_activity() -> None:
    habits = adaptive_service.summarize_habits([], [], NOW, 7)
    assert habits["active_days"] == 0
    assert habits["peak_hour"] is None
    assert habits["preferred_skill"] is None
    assert habits["studied_today"] is False
    assert habits["progress_trend"] == "insufficient_data"


def test_summarize_habits_uses_study_timezone_for_peak_hour_and_today() -> None:
    # 14:00 UTC = 21:00 ở UTC+7; hai buổi cùng ngày chỉ tính 1 ngày học.
    events = [
        ("reading", NOW.replace(hour=14)),
        ("reading", NOW.replace(hour=14, minute=30)),
        ("vocabulary", NOW - timedelta(days=1)),
    ]
    habits = adaptive_service.summarize_habits(events, [], NOW, 7)
    assert habits["active_days"] == 2
    assert habits["peak_hour"] == 21
    assert habits["preferred_skill"] == "reading"
    assert habits["studied_today"] is True
    assert habits["activities_per_active_day"] == 1.5


def test_summarize_habits_progress_trend_from_quiz_scores() -> None:
    improving = adaptive_service.summarize_habits([], [90, 90, 90, 90, 90, 60, 60, 60, 60, 60], NOW, 7)
    assert improving["progress_trend"] == "improving"
    assert improving["quiz_score_change"] == 30
    declining = adaptive_service.summarize_habits([], [50] * 5 + [80] * 5, NOW, 7)
    assert declining["progress_trend"] == "declining"
    stable = adaptive_service.summarize_habits([], [70] * 10, NOW, 7)
    assert stable["progress_trend"] == "stable"


def test_record_error_rejects_unknown_type() -> None:
    with pytest.raises(ValueError):
        adaptive_service.record_error(None, uuid.uuid4(), "made_up_type")  # type: ignore[arg-type]


# ---------- Tích hợp qua API (cần PostgreSQL đã chạy migration 0013) ----------


@pytest.fixture
def adaptive_client() -> Generator[TestClient, None, None]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.session_factory = session_factory  # type: ignore[attr-defined]
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        asyncio.run(engine.dispose())


def login(client: TestClient) -> tuple[dict[str, str], uuid.UUID]:
    email = f"adaptive_{uuid.uuid4().hex[:12]}@example.com"
    assert client.post(
        "/api/auth/register", json={"email": email, "password": "StrongPass123", "target_level": "b1"}
    ).status_code == 201
    token = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = uuid.UUID(client.get("/api/users/me", headers=headers).json()["id"])
    return headers, user_id


def seed_errors(client: TestClient, user_id: uuid.UUID, error_types: list[str]) -> None:
    async def run() -> None:
        async with client.session_factory() as session:  # type: ignore[attr-defined]
            for error_type in error_types:
                session.add(UserError(user_id=user_id, error_type=error_type, detail={"source": "writing", "original_text": "he go"}))
            await session.commit()

    asyncio.run(run())


def fake_quiz(sources: list[dict], num_questions: int) -> list[dict]:
    return [
        {
            "source_index": index % len(sources),
            "question_text": f"Question {index}",
            "options": ["a", "b", "c", "d"],
            "correct_option_index": 1,
            "explanation": "because",
        }
        for index in range(num_questions)
    ]


def test_adaptive_endpoints_require_authentication(adaptive_client: TestClient) -> None:
    for path in ("/api/adaptive/errors", "/api/adaptive/review-queue", "/api/adaptive/habits"):
        assert adaptive_client.get(path).status_code == 401
    assert adaptive_client.post("/api/adaptive/quizzes/generate", json={}).status_code == 401


def test_new_user_has_empty_engine_state(adaptive_client: TestClient) -> None:
    headers, _ = login(adaptive_client)
    assert adaptive_client.get("/api/adaptive/errors", headers=headers).json() == []
    assert adaptive_client.get("/api/adaptive/review-queue", headers=headers).json() == []
    habits = adaptive_client.get("/api/adaptive/habits", headers=headers).json()
    assert habits["active_days"] == 0
    assert habits["progress_trend"] == "insufficient_data"


def test_errors_are_listed_filtered_and_scoped_to_owner(adaptive_client: TestClient) -> None:
    headers, user_id = login(adaptive_client)
    other_headers, _ = login(adaptive_client)
    seed_errors(adaptive_client, user_id, ["grammar", "grammar", "spelling"])

    everything = adaptive_client.get("/api/adaptive/errors", headers=headers).json()
    assert len(everything) == 3
    scores = [error["priority_score"] for error in everything]
    assert scores == sorted(scores, reverse=True)

    grammar_only = adaptive_client.get("/api/adaptive/errors?error_type=grammar", headers=headers).json()
    assert {error["error_type"] for error in grammar_only} == {"grammar"}

    assert adaptive_client.get("/api/adaptive/errors", headers=other_headers).json() == []


def test_review_queue_contains_user_errors(adaptive_client: TestClient) -> None:
    headers, user_id = login(adaptive_client)
    seed_errors(adaptive_client, user_id, ["vocabulary", "grammar"])
    queue = adaptive_client.get("/api/adaptive/review-queue", headers=headers).json()
    assert {item["item_type"] for item in queue} == {"error"}
    assert {item["label"] for item in queue} == {"vocabulary", "grammar"}
    # Gọi lại tính lại từ đầu chứ không nhân đôi hàng đợi.
    assert len(adaptive_client.get("/api/adaptive/review-queue", headers=headers).json()) == 2


def test_quiz_generate_without_errors_uses_fallback_topics(
    adaptive_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_generate(sources: list[dict], num_questions: int) -> list[dict]:
        assert all(source["id"] is None for source in sources)
        return fake_quiz(sources, num_questions)

    monkeypatch.setattr(llm_service, "generate_adaptive_quiz", fake_generate)
    monkeypatch.setattr(adaptive_service, "shuffle_options", lambda questions: None)  # đáp án đúng cố định = 1
    headers, _ = login(adaptive_client)
    response = adaptive_client.post("/api/adaptive/quizzes/generate", headers=headers, json={"num_questions": 4})
    assert response.status_code == 201
    quiz = response.json()
    assert len(quiz["questions"]) == 4
    # Câu sai của đề dự phòng vẫn ghi lỗi mới để lần sau có dữ liệu thật; câu đúng không lỗi.
    answers = [1, 0, 1, 0]
    attempt = adaptive_client.post(
        f"/api/adaptive/quizzes/{quiz['quiz_id']}/attempts", headers=headers, json={"answers": answers}
    )
    assert attempt.status_code == 200
    assert attempt.json()["score"] == 50
    assert len(adaptive_client.get("/api/adaptive/errors", headers=headers).json()) == 2


def test_quiz_generate_without_errors_and_unsupported_focus_returns_conflict(
    adaptive_client: TestClient,
) -> None:
    headers, _ = login(adaptive_client)
    response = adaptive_client.post(
        "/api/adaptive/quizzes/generate", headers=headers, json={"focus_error_types": ["pronunciation"]}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "no_errors_to_practice"


def test_broken_streak_is_restored_by_a_long_enough_passing_quiz(
    adaptive_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_generate(sources: list[dict], num_questions: int) -> list[dict]:
        return fake_quiz(sources, num_questions)

    monkeypatch.setattr(llm_service, "generate_adaptive_quiz", fake_generate)
    monkeypatch.setattr(adaptive_service, "shuffle_options", lambda questions: None)  # đáp án đúng cố định = 1
    headers, user_id = login(adaptive_client)

    async def seed_broken_streak() -> None:
        async with adaptive_client.session_factory() as session:  # type: ignore[attr-defined]
            today = datetime.now(timezone.utc).date()
            session.add(Streak(user_id=user_id, current_streak=5, longest_streak=5, last_active_date=today - timedelta(days=4)))
            await session.commit()

    asyncio.run(seed_broken_streak())
    assert adaptive_client.get("/api/streaks", headers=headers).json()["restorable_streak"] == 5

    def attempt(num_questions: int, answer: int) -> dict:
        quiz = adaptive_client.post(
            "/api/adaptive/quizzes/generate", headers=headers, json={"num_questions": num_questions}
        ).json()
        return adaptive_client.post(
            f"/api/adaptive/quizzes/{quiz['quiz_id']}/attempts",
            headers=headers,
            json={"answers": [answer] * num_questions},
        ).json()

    # Đề quá ngắn hoặc điểm thấp thì không khôi phục (đáp án đúng của fake_quiz luôn là 1).
    assert attempt(5, 1)["streak_restored"] is False
    assert attempt(10, 0)["streak_restored"] is False
    assert attempt(10, 1)["streak_restored"] is True

    streak = adaptive_client.get("/api/streaks", headers=headers).json()
    # 5 ngày cũ + hôm nay; chỉ khôi phục được 1 lần.
    assert streak["current_streak"] == 6 and streak["restorable_streak"] == 0
    assert attempt(10, 1)["streak_restored"] is False


def test_quiz_generate_rejects_unknown_focus_type(adaptive_client: TestClient) -> None:
    headers, _ = login(adaptive_client)
    response = adaptive_client.post(
        "/api/adaptive/quizzes/generate", headers=headers, json={"focus_error_types": ["nonsense"]}
    )
    assert response.status_code == 422


def test_quiz_flow_hides_answers_grades_and_updates_errors(
    adaptive_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_generate(sources: list[dict], num_questions: int) -> list[dict]:
        return fake_quiz(sources, num_questions)

    monkeypatch.setattr(llm_service, "generate_adaptive_quiz", fake_generate)
    # Test này nộp đáp án cố định theo fake_quiz (đúng = index 1), nên tắt xáo trộn ở đây.
    monkeypatch.setattr(adaptive_service, "shuffle_options", lambda questions: None)
    headers, user_id = login(adaptive_client)
    seed_errors(adaptive_client, user_id, ["grammar", "spelling"])

    created = adaptive_client.post(
        "/api/adaptive/quizzes/generate", headers=headers, json={"num_questions": 2}
    )
    assert created.status_code == 201
    body = created.json()
    assert len(body["questions"]) == 2
    assert all("correct_option_index" not in question for question in body["questions"])

    quiz_id = body["quiz_id"]
    # Câu 1 đúng (đáp án 1), câu 2 sai.
    attempt = adaptive_client.post(f"/api/adaptive/quizzes/{quiz_id}/attempts", headers=headers, json={"answers": [1, 0]})
    assert attempt.status_code == 200
    graded = attempt.json()
    assert graded["score"] == 50.0
    assert [result["is_correct"] for result in graded["results"]] == [True, False]
    assert graded["results"][0]["correct_option_index"] == 1

    # Lỗi mới do trả lời sai được ghi kèm quiz_attempt_id -> tổng số lỗi tăng 1.
    assert len(adaptive_client.get("/api/adaptive/errors", headers=headers).json()) == 3
    # Chỉ lần đầu làm đề nhận XP; làm lại cùng đề không nhận thêm.
    assert adaptive_client.get("/api/streaks", headers=headers).json()["total_xp"] == 25
    adaptive_client.post(f"/api/adaptive/quizzes/{quiz_id}/attempts", headers=headers, json={"answers": [1, 1]})
    assert adaptive_client.get("/api/streaks", headers=headers).json()["total_xp"] == 25

    habits = adaptive_client.get("/api/adaptive/habits", headers=headers).json()
    assert habits["activity_by_skill"]["quiz"] == 2


def test_quiz_attempt_validation_and_ownership(adaptive_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_generate(sources: list[dict], num_questions: int) -> list[dict]:
        return fake_quiz(sources, num_questions)

    monkeypatch.setattr(llm_service, "generate_adaptive_quiz", fake_generate)
    headers, user_id = login(adaptive_client)
    other_headers, _ = login(adaptive_client)
    seed_errors(adaptive_client, user_id, ["grammar"])

    quiz_id = adaptive_client.post(
        "/api/adaptive/quizzes/generate", headers=headers, json={"num_questions": 2}
    ).json()["quiz_id"]

    wrong_count = adaptive_client.post(f"/api/adaptive/quizzes/{quiz_id}/attempts", headers=headers, json={"answers": [1]})
    assert wrong_count.status_code == 422
    # Quiz của người khác trả 404 giống quiz không tồn tại, không lộ sự tồn tại của nó.
    foreign = adaptive_client.post(f"/api/adaptive/quizzes/{quiz_id}/attempts", headers=other_headers, json={"answers": [1, 1]})
    assert foreign.status_code == 404
    missing = adaptive_client.post(f"/api/adaptive/quizzes/{uuid.uuid4()}/attempts", headers=headers, json={"answers": [1, 1]})
    assert missing.status_code == 404


def test_quiz_generate_reports_llm_outage(adaptive_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def down(*_args, **_kwargs):
        raise llm_service.AIServiceError("offline")

    monkeypatch.setattr(llm_service, "generate_adaptive_quiz", down)
    headers, user_id = login(adaptive_client)
    seed_errors(adaptive_client, user_id, ["grammar"])
    response = adaptive_client.post("/api/adaptive/quizzes/generate", headers=headers, json={})
    assert response.status_code == 503
