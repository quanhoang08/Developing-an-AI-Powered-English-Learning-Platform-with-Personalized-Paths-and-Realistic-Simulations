"""Streak + XP: cộng khi user HOÀN THÀNH một hoạt động học, đọc lại qua GET /api/streaks.

Quy ước (test-cases AL-007/AL-008): một "ngày học" là ngày có ít nhất một hoạt động hoàn thành;
bỏ qua 1 ngày thì streak về 1 ở lần học kế tiếp, longest_streak giữ nguyên. Ngày tính theo múi
giờ học cố định (settings.study_utc_offset_hours, mặc định UTC+7) chứ không theo UTC để một buổi
học tối ở Việt Nam không bị tính sang ngày hôm sau.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.gamification import SkillProgress, Streak


# XP mỗi hoạt động hoàn thành. Số điểm là quy ước của đề tài (spec chưa quy định), đặt cao hơn
# cho việc tốn công hơn: nộp bài viết > hoàn thành bài đọc > dictation > nói 1 lượt > ôn 1 từ.
XP_BY_ACTIVITY: dict[str, int] = {
	"vocab_review": 5,
	"reading_completed": 20,
	"writing_submitted": 30,
	"dictation_completed": 15,
	"speaking_turn": 10,
	"quiz_completed": 25,
}


# Hoạt động → kỹ năng ghi vào skill_progress (vocab_review/quiz_completed không thuộc 1 kỹ năng nào).
SKILL_BY_ACTIVITY: dict[str, str] = {
	"reading_completed": "reading",
	"dictation_completed": "listening",
	"writing_submitted": "writing",
	"speaking_turn": "speaking",
}
# Trọng số của điểm mới trong trung bình động: 0.3 → mỗi bài mới chiếm 30%, bài cũ phai dần.
SKILL_SCORE_WEIGHT = 0.3


def study_today(now: datetime | None = None) -> date:
	"""Ngày học hiện tại theo múi giờ cấu hình (nhận `now` để test cố định thời điểm)."""
	current = now or datetime.now(timezone.utc)
	offset = timedelta(hours=get_settings().study_utc_offset_hours)
	return (current.astimezone(timezone.utc) + offset).date()


def level_threshold(level: int) -> int:
	"""Tổng XP tối thiểu để đạt `level`: 0, 100, 300, 600, 1000... (mỗi level cần thêm 100*level XP)."""
	return 50 * level * (level - 1)


def level_from_xp(total_xp: int) -> tuple[int, int, int]:
	"""Trả (level, xp_into_level, xp_for_next_level) từ tổng XP."""
	level = 1
	while total_xp >= level_threshold(level + 1):
		level += 1
	return level, total_xp - level_threshold(level), level_threshold(level + 1) - level_threshold(level)


def next_streak(current: int, last_active: date | None, today: date) -> int:
	"""Độ dài chuỗi sau khi có hoạt động vào `today`."""
	if last_active == today:
		return max(current, 1)
	if last_active == today - timedelta(days=1):
		return current + 1
	return 1


def visible_streak(current: int, last_active: date | None, today: date) -> int:
	"""Streak hiển thị: chuỗi còn sống nếu học hôm qua hoặc hôm nay, ngược lại đã đứt (0)."""
	if last_active is not None and last_active >= today - timedelta(days=1):
		return current
	return 0


async def record_skill_score(
	db: AsyncSession, user_id: uuid.UUID, skill: str, score: float, cefr_level: str | None = None
) -> None:
	"""Cập nhật điểm trung bình động của 1 kỹ năng (score thang 0-100). KHÔNG commit.

	Upsert nguyên tử trong SQL nên hai request đồng thời không ghi đè nhau; cefr_level NULL giữ
	nguyên giá trị cũ.
	"""
	score = min(max(float(score), 0.0), 100.0)
	insert = pg_insert(SkillProgress).values(user_id=user_id, skill_name=skill, score=score, cefr_level=cefr_level)
	await db.execute(
		insert.on_conflict_do_update(
			index_elements=["user_id", "skill_name"],
			set_={
				"score": SkillProgress.score * (1 - SKILL_SCORE_WEIGHT) + insert.excluded.score * SKILL_SCORE_WEIGHT,
				"cefr_level": func.coalesce(insert.excluded.cefr_level, SkillProgress.cefr_level),
			},
		)
	)


async def list_skill_progress(db: AsyncSession, user_id: uuid.UUID) -> list[SkillProgress]:
	"""Kỹ năng user đã có điểm, theo thứ tự cố định reading → listening → writing → speaking."""
	rows = (await db.scalars(select(SkillProgress).where(SkillProgress.user_id == user_id))).all()
	order = list(SKILL_BY_ACTIVITY.values())
	return sorted(rows, key=lambda row: order.index(row.skill_name) if row.skill_name in order else len(order))


async def award_activity(
	db: AsyncSession,
	user_id: uuid.UUID,
	activity: str,
	now: datetime | None = None,
	score: float | None = None,
	cefr_level: str | None = None,
) -> None:
	"""Cộng XP và cập nhật streak; nếu hoạt động thuộc 1 kỹ năng và có `score` (thang 0-100) thì
	cập nhật luôn skill_progress. KHÔNG commit — gọi cùng transaction với việc lưu kết quả
	hoạt động để hoặc cả hai cùng được ghi, hoặc cả hai cùng bị huỷ."""
	xp = XP_BY_ACTIVITY[activity]
	if score is not None and activity in SKILL_BY_ACTIVITY:
		await record_skill_score(db, user_id, SKILL_BY_ACTIVITY[activity], score, cefr_level)
	today = study_today(now)

	# Tạo dòng nếu user chưa có (ON CONFLICT tránh lỗi khi 2 request đầu tiên chạy song song),
	# rồi khoá dòng để hai hoạt động đồng thời không cộng đè lên nhau.
	await db.execute(pg_insert(Streak).values(user_id=user_id).on_conflict_do_nothing(index_elements=["user_id"]))
	streak = await db.scalar(select(Streak).where(Streak.user_id == user_id).with_for_update())

	streak.current_streak = next_streak(streak.current_streak or 0, streak.last_active_date, today)
	streak.longest_streak = max(streak.longest_streak or 0, streak.current_streak)
	streak.last_active_date = today
	streak.total_xp = (streak.total_xp or 0) + xp


async def get_summary(db: AsyncSession, user_id: uuid.UUID, now: datetime | None = None) -> dict:
	"""Số liệu cho GET /api/streaks; user chưa học lần nào trả toàn số 0 (không tạo dòng mới)."""
	today = study_today(now)
	streak = await db.scalar(select(Streak).where(Streak.user_id == user_id))

	total_xp = (streak.total_xp or 0) if streak else 0
	last_active = streak.last_active_date if streak else None
	current = visible_streak(streak.current_streak or 0, last_active, today) if streak else 0
	level, xp_into_level, xp_for_next_level = level_from_xp(total_xp)

	# Chuỗi hiện tại kết thúc ở last_active_date và dài `current` ngày.
	recent_dates = (
		[last_active - timedelta(days=offset) for offset in range(current - 1, -1, -1)]
		if current > 0 and last_active is not None
		else []
	)
	return {
		"current_streak": current,
		"longest_streak": max((streak.longest_streak or 0) if streak else 0, current),
		"last_active_date": last_active,
		"today_active": last_active == today,
		"total_xp": total_xp,
		"level": level,
		"xp_into_level": xp_into_level,
		"xp_for_next_level": xp_for_next_level,
		"recent_active_dates": recent_dates,
	}
