import asyncio
import uuid
from collections.abc import Generator
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.database import get_db
from app.main import app
from app.services import gamification_service as gamification


# ---------- Logic thuần (không cần DB) ----------


def test_level_thresholds_grow_by_100_per_level() -> None:
    assert gamification.level_from_xp(0) == (1, 0, 100)
    assert gamification.level_from_xp(99) == (1, 99, 100)
    assert gamification.level_from_xp(100) == (2, 0, 200)
    assert gamification.level_from_xp(299) == (2, 199, 200)
    assert gamification.level_from_xp(300) == (3, 0, 300)


def test_next_streak_continues_keeps_or_resets() -> None:
    today = date(2026, 9, 20)
    # Lần học đầu tiên và sau khi bỏ >= 1 ngày đều bắt đầu lại từ 1 (AL-008).
    assert gamification.next_streak(0, None, today) == 1
    assert gamification.next_streak(9, date(2026, 9, 18), today) == 1
    # Học liền ngày hôm qua thì nối chuỗi.
    assert gamification.next_streak(9, date(2026, 9, 19), today) == 10
    # Học nhiều lần trong cùng một ngày không cộng thêm.
    assert gamification.next_streak(9, today, today) == 9


def test_visible_streak_expires_after_a_missed_day() -> None:
    today = date(2026, 9, 20)
    assert gamification.visible_streak(5, today, today) == 5
    assert gamification.visible_streak(5, date(2026, 9, 19), today) == 5
    assert gamification.visible_streak(5, date(2026, 9, 18), today) == 0
    assert gamification.visible_streak(0, None, today) == 0


def test_study_day_uses_configured_utc_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gamification, "get_settings", lambda: SimpleNamespace(study_utc_offset_hours=7))
    # 18:00 UTC ngày 19 = 01:00 ngày 20 ở UTC+7 -> phải tính sang ngày 20.
    assert gamification.study_today(datetime(2026, 9, 19, 18, 0, tzinfo=timezone.utc)) == date(2026, 9, 20)
    assert gamification.study_today(datetime(2026, 9, 19, 16, 59, tzinfo=timezone.utc)) == date(2026, 9, 19)


# ---------- Tích hợp qua API (cần PostgreSQL như các integration test khác) ----------


@pytest.fixture
def gamification_client() -> Generator[TestClient, None, None]:
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
    email = f"gamification_{uuid.uuid4().hex[:12]}@example.com"
    assert client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPass123", "target_level": "b1"},
    ).status_code == 201
    response = client.post("/api/auth/login", json={"email": email, "password": "StrongPass123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_streaks_require_authentication(gamification_client: TestClient) -> None:
    assert gamification_client.get("/api/streaks").status_code == 401


def test_new_user_has_zero_streak_and_xp(gamification_client: TestClient) -> None:
    headers = login(gamification_client)
    body = gamification_client.get("/api/streaks", headers=headers).json()
    assert body["current_streak"] == 0
    assert body["longest_streak"] == 0
    assert body["last_active_date"] is None
    assert body["today_active"] is False
    assert body["total_xp"] == 0
    assert body["level"] == 1
    assert body["recent_active_dates"] == []


def test_due_vocab_review_awards_xp_and_starts_streak_once_per_card(gamification_client: TestClient) -> None:
    headers = login(gamification_client)
    created = gamification_client.post(
        "/api/vocab",
        headers=headers,
        json={"term": "pervasive", "definition": "widespread", "source_url": "https://example.com/a"},
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    # Thẻ mới đến hạn ngay: ôn lần đầu được +5 XP và mở streak 1 ngày.
    assert gamification_client.post(
        f"/api/vocab/{item_id}/review", headers=headers, json={"quality": 4}
    ).status_code == 200
    first = gamification_client.get("/api/streaks", headers=headers).json()
    assert first["current_streak"] == 1
    assert first["longest_streak"] == 1
    assert first["today_active"] is True
    assert first["total_xp"] == gamification.XP_BY_ACTIVITY["vocab_review"]
    assert len(first["recent_active_dates"]) == 1

    # Ôn lại đúng thẻ đó khi chưa đến hạn không được cộng thêm XP (chống cày XP).
    assert gamification_client.post(
        f"/api/vocab/{item_id}/review", headers=headers, json={"quality": 4}
    ).status_code == 200
    second = gamification_client.get("/api/streaks", headers=headers).json()
    assert second["total_xp"] == first["total_xp"]
    assert second["current_streak"] == 1


def _award(gamification_client: TestClient, user_id: str, activity: str, **kwargs) -> None:
    # Gọi thẳng service (giống cách các module kỹ năng gọi) trên session riêng, commit như router.
    async def run() -> None:
        settings = get_settings()
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
                await gamification.award_activity(session, uuid.UUID(user_id), activity, **kwargs)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_skills_require_authentication_and_new_user_has_none(gamification_client: TestClient) -> None:
    assert gamification_client.get("/api/skills").status_code == 401
    assert gamification_client.get("/api/skills", headers=login(gamification_client)).json() == []


def test_skill_progress_is_moving_average_and_keeps_cefr(gamification_client: TestClient) -> None:
    headers = login(gamification_client)
    user_id = gamification_client.get("/api/users/me", headers=headers).json()["id"]

    _award(gamification_client, user_id, "writing_submitted", score=80, cefr_level="B2")
    _award(gamification_client, user_id, "reading_completed", score=50)
    # Điểm mới chiếm 30%: 80*0.7 + 20*0.3 = 62; cefr_level NULL không xoá giá trị cũ.
    _award(gamification_client, user_id, "writing_submitted", score=20)
    # Hoạt động không thuộc kỹ năng nào (ôn từ) không tạo dòng skill_progress.
    _award(gamification_client, user_id, "vocab_review", score=100)

    skills = gamification_client.get("/api/skills", headers=headers).json()
    assert [(row["skill_name"], row["score"], row["cefr_level"]) for row in skills] == [
        ("reading", 50.0, None),
        ("writing", 62.0, "B2"),
    ]
