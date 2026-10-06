from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.services.study_plan_service import pick_daily_minutes
from tests.test_vocab_integration import login, vocab_client  # noqa: F401  (fixture)


def test_pick_daily_minutes_bounds() -> None:
	assert pick_daily_minutes(None, None) == 30
	assert pick_daily_minutes(1.0, 20) == 65
	assert pick_daily_minutes(9.0, 5) == 90


def test_goal_saved_and_plan_returned(vocab_client: TestClient) -> None:
	headers = login(vocab_client)
	exam = (date.today() + timedelta(days=45)).isoformat()
	patched = vocab_client.patch("/api/users/me", headers=headers, json={"target_band": 7.0, "exam_date": exam})
	assert patched.status_code == 200 and patched.json()["target_band"] == 7.0
	assert vocab_client.patch("/api/users/me", headers=headers, json={"target_band": 6.3}).status_code == 422

	plan = vocab_client.get("/api/users/me/study-plan", headers=headers).json()
	assert plan["days_left"] == 45 and plan["current_band"] is None
	assert sum(t["minutes"] for t in plan["daily_tasks"]) == plan["daily_minutes"]
	assert any("mock test" in note for note in plan["notes"])
