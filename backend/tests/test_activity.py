"""Timer mode toggle + Dashboard "This week, in minutes" / "Pick up where you left off".

LLM/TTS không liên quan tới logic này nên không cần giả — award_activity/activity_service chỉ
đọc/ghi DB thật. Reading/Writing/Dictation/Speaking được tạo trực tiếp qua model (bỏ qua luồng
sinh nội dung bằng Gemini/Azure) để test đúng phần join/tính toán, không test lại luồng tạo bài.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.gamification import StudyTimeLog
from app.models.listening import DictationAttempt, Podcast
from app.models.notebook import Document
from app.models.reading import ReadingSession
from app.models.speaking import ConversationSession, ConversationTurn, Scenario
from app.models.writing import WritingSubmission
from app.services import gamification_service
from tests.test_rearrange_integration import _login, client, session_factory  # noqa: F401


def _run(coro):
	return asyncio.run(coro)


def test_timer_mode_defaults_off_and_can_be_toggled(client: TestClient) -> None:
	headers = _login(client)
	me = client.get("/api/users/me", headers=headers).json()
	assert me["timer_mode_enabled"] is False

	patched = client.patch("/api/users/me", headers=headers, json={"timer_mode_enabled": True})
	assert patched.status_code == 200
	assert patched.json()["timer_mode_enabled"] is True
	# Bền qua GET tiếp theo, không chỉ trong response của PATCH.
	assert client.get("/api/users/me", headers=headers).json()["timer_mode_enabled"] is True


def test_weekly_summary_zero_for_new_user(client: TestClient) -> None:
	headers = _login(client)
	body = client.get("/api/activity/weekly-summary", headers=headers).json()
	assert body["timer_mode_enabled"] is False
	assert body["minutes_by_skill"] == {"reading": 0, "listening": 0, "writing": 0, "speaking": 0}
	assert body["total_minutes"] == 0


def test_weekly_summary_only_counts_activity_with_duration(
	client: TestClient, session_factory: async_sessionmaker
) -> None:
	headers = _login(client)
	user_id = uuid.UUID(client.get("/api/users/me", headers=headers).json()["id"])

	async def award() -> None:
		async with session_factory() as session:
			# Số giây chia hết cho 60 để tránh phụ thuộc cách làm tròn phút .5 (banker's rounding).
			await gamification_service.award_activity(
				session, user_id, "reading_completed", score=80, duration_seconds=120
			)
			await gamification_service.award_activity(
				session, user_id, "writing_submitted", score=70, duration_seconds=180
			)
			# Không bấm giờ (duration_seconds=None): không được cộng vào phút học tuần này.
			await gamification_service.award_activity(session, user_id, "dictation_completed", score=60)
			await session.commit()

	_run(award())

	body = client.get("/api/activity/weekly-summary", headers=headers).json()
	assert body["minutes_by_skill"] == {"reading": 2, "listening": 0, "writing": 3, "speaking": 0}
	assert body["total_minutes"] == 5


def test_weekly_summary_ignores_activity_older_than_7_days(
	client: TestClient, session_factory: async_sessionmaker
) -> None:
	headers = _login(client)
	user_id = uuid.UUID(client.get("/api/users/me", headers=headers).json()["id"])
	old_created_at = datetime.now(timezone.utc) - timedelta(days=10)

	async def award_old() -> None:
		async with session_factory() as session:
			await gamification_service.award_activity(session, user_id, "speaking_turn", duration_seconds=600)
			await session.flush()
			await session.execute(
				StudyTimeLog.__table__.update()
				.where(StudyTimeLog.user_id == user_id)
				.values(created_at=old_created_at)
			)
			await session.commit()

	_run(award_old())

	body = client.get("/api/activity/weekly-summary", headers=headers).json()
	assert body["minutes_by_skill"]["speaking"] == 0
	assert body["total_minutes"] == 0


def test_recent_activity_empty_for_new_user(client: TestClient) -> None:
	headers = _login(client)
	assert client.get("/api/activity/recent", headers=headers).json() == []


def test_recent_activity_merges_skills_by_most_recent_first(
	client: TestClient, session_factory: async_sessionmaker
) -> None:
	headers = _login(client)
	user_id = uuid.UUID(client.get("/api/users/me", headers=headers).json()["id"])
	now = datetime.now(timezone.utc)

	async def seed() -> None:
		async with session_factory() as session:
			document = Document(user_id=user_id, title="Business English", source_type="docx", status="ready")
			session.add(document)
			await session.flush()

			session.add(
				WritingSubmission(
					user_id=user_id,
					source_type="free_topic",
					prompt_text="Describe your hometown.",
					submitted_text="My hometown is...",
					overall_score=72,
					cefr_level="B2",
					ielts_band="6.0",
					completed_at=now - timedelta(hours=1),
				)
			)
			session.add(
				ReadingSession(
					user_id=user_id,
					document_id=document.id,
					mode="classic",
					score=0.8,
					completed_at=now - timedelta(hours=3),
				)
			)
			# Chưa nộp (completed_at NULL) — KHÔNG được xuất hiện trong recent activity.
			session.add(ReadingSession(user_id=user_id, document_id=document.id, mode="classic"))

			podcast = Podcast(document_id=document.id, script_text="...", status="ready")
			session.add(podcast)
			await session.flush()
			session.add(
				DictationAttempt(
					podcast_id=podcast.id,
					user_id=user_id,
					start_word_index=0,
					end_word_index=5,
					user_input_text="the cat sat",
					accuracy_score=90,
					created_at=now - timedelta(minutes=30),
				)
			)

			scenario = Scenario(title="Ordering coffee", formality_level="casual")
			session.add(scenario)
			await session.flush()
			speaking_session = ConversationSession(
				user_id=user_id, scenario_id=scenario.id, started_at=now - timedelta(days=1)
			)
			session.add(speaking_session)
			await session.flush()
			session.add(
				ConversationTurn(conversation_session_id=speaking_session.id, turn_index=0, ai_response_text="Hi!")
			)
			await session.commit()

	_run(seed())

	items = client.get("/api/activity/recent", headers=headers, params={"limit": 10}).json()
	skills_in_order = [item["skill"] for item in items]
	# Mới nhất trước: dictation (30 phút trước) -> writing (1h) -> reading (3h) -> speaking (1 ngày).
	assert skills_in_order == ["listening", "writing", "reading", "speaking"]
	assert items[0]["title"] == "Dictation — Business English"
	assert items[0]["score"] == 90.0
	assert items[2]["score"] == 80.0  # 0.8 * 100
	assert items[3]["score"] is None  # speaking chưa có điểm tổng theo phiên
