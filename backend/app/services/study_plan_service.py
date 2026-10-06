# Backlog 2.5: kế hoạch học theo band mục tiêu + ngày thi. Luật cố định, không gọi LLM.
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.speaking import IeltsAttempt
from app.models.user import User

_CRITERIA = {
	"fluency_coherence": ("speaking", "Speaking practice: answer 2 IELTS Part 1/2 questions aloud, then review your fillers and speed"),
	"lexical_resource": ("vocabulary", "Review your SM-2 words and write 3 sentences with new words (Use it in a sentence)"),
	"grammatical_range": ("writing", "Write one paragraph and check its sentence structures (Grammatical Range card)"),
	"pronunciation": ("speaking", "Pronunciation drill: read 5 sentences and fix the lowest-scoring sounds"),
}


def pick_daily_minutes(band_gap: float | None, days_left: int | None) -> int:
	"""Khoảng cách band lớn và ngày thi gần thì học nhiều hơn; trần 90 phút, sàn 20 phút."""
	minutes = 30 + (int(band_gap * 20) if band_gap and band_gap > 0 else 0)
	if days_left is not None and days_left <= 30:
		minutes += 15
	return max(20, min(90, minutes))


async def build_plan(db: AsyncSession, user: User, today: date | None = None) -> dict:
	today = today or date.today()
	target = float(user.target_band) if user.target_band is not None else None
	days_left = (user.exam_date - today).days if user.exam_date else None
	latest = await db.scalar(
		select(IeltsAttempt).where(IeltsAttempt.user_id == user.id).order_by(IeltsAttempt.created_at.desc()).limit(1)
	)
	current = float(latest.overall) if latest else None
	gap = round(target - current, 1) if target is not None and current is not None else None

	weakest = None
	if latest:
		scores = {key: getattr(latest, key) for key in _CRITERIA}
		scores = {key: float(value) for key, value in scores.items() if value is not None}
		weakest = min(scores, key=scores.get)

	minutes = pick_daily_minutes(gap, days_left)
	notes = []
	if target is None:
		notes.append("Set a target band to get a plan.")
	if current is None:
		notes.append("Take an IELTS Speaking mock test so the plan can measure your gap (band is an estimate).")
	if days_left is not None and days_left < 0:
		notes.append("Your exam date has passed — update it.")
	elif days_left is not None and gap is not None and gap > 0 and days_left < gap * 60:
		notes.append("Little time for this gap (roughly 2 months per +1.0 band) — consider a later exam date.")

	skill, task = _CRITERIA[weakest] if weakest else ("speaking", "Take an IELTS Speaking mock test")
	tasks = [
		{"skill": "vocabulary", "task": "Review your due SM-2 words", "minutes": max(5, minutes // 6)},
		{"skill": skill, "task": task, "minutes": minutes // 2},
		{"skill": "reading", "task": "One Skim & Scan session (try True/False/Not Given)", "minutes": minutes // 4},
	]
	tasks[-1]["minutes"] = minutes - tasks[0]["minutes"] - tasks[1]["minutes"]
	return {
		"target_band": target,
		"exam_date": user.exam_date,
		"days_left": days_left,
		"current_band": current,
		"band_gap": gap,
		"weakest_criterion": weakest,
		"daily_minutes": minutes,
		"daily_tasks": tasks,
		"notes": notes,
	}
