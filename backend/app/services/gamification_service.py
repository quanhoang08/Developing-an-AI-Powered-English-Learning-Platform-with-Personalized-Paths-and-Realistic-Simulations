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
from app.models.gamification import ActivityLog, SkillProgress, Streak, StudyTimeLog


# XP mỗi hoạt động hoàn thành. Số điểm là quy ước của đề tài (spec chưa quy định), đặt cao hơn
# cho việc tốn công hơn: nộp bài viết > hoàn thành bài đọc > dictation > nói 1 lượt > ôn 1 từ.
XP_BY_ACTIVITY: dict[str, int] = {
	"vocab_review": 5,
	"reading_completed": 20,
	"writing_submitted": 30,
	"dictation_completed": 15,
	"listening_quiz_completed": 15,
	"toeic_listening_completed": 15,
	"toeic_reading_completed": 15,
	"speaking_turn": 10,
	"pronunciation_practice": 8,
	"speaking_silent": 3,  # gõ thay nói (backlog 4.5): ít XP hơn nói thật
	"quiz_completed": 25,
}


# Hoạt động → kỹ năng ghi vào skill_progress (vocab_review/quiz_completed không thuộc 1 kỹ năng nào).
SKILL_BY_ACTIVITY: dict[str, str] = {
	"reading_completed": "reading",
	"dictation_completed": "listening",
	"listening_quiz_completed": "listening",
	"toeic_listening_completed": "listening",
	"toeic_reading_completed": "reading",
	"writing_submitted": "writing",
	"speaking_turn": "speaking",
	"pronunciation_practice": "speaking",
}
# Trọng số của điểm mới trong trung bình động: 0.3 → mỗi bài mới chiếm 30%, bài cũ phai dần.
SKILL_SCORE_WEIGHT = 0.3

# Khôi phục chuỗi đứt bằng quiz: chuỗi đủ dài mới đáng khôi phục, quiz 10-15 câu, đạt >= 70%.
MIN_RESTORABLE_STREAK = 2
# Freeze: mỗi 7 ngày liên tiếp được tặng 1, giữ tối đa 2; tự dùng khi bỏ lỡ ngày.
FREEZE_EVERY_DAYS = 7
MAX_FREEZES = 2
RESTORE_MIN_QUESTIONS = 10
RESTORE_MIN_SCORE = 70


def study_today(now: datetime | None = None) -> date:
	"""Ngày học hiện tại theo múi giờ cấu hình (nhận `now` để test cố định thời điểm)."""
	current = now or datetime.now(timezone.utc)
	offset = timedelta(hours=get_settings().study_utc_offset_hours)
	return (current.astimezone(timezone.utc) + offset).date()


def week_start(now: datetime | None = None) -> datetime:
	"""0h thứ Hai của tuần học hiện tại (theo múi giờ học), trả về dạng UTC để so với created_at."""
	today = study_today(now)
	offset = timedelta(hours=get_settings().study_utc_offset_hours)
	monday = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time(), tzinfo=timezone.utc)
	return monday - offset


def day_start(now: datetime | None = None) -> datetime:
	"""0h hôm nay theo múi giờ học, trả về dạng UTC để so với created_at."""
	offset = timedelta(hours=get_settings().study_utc_offset_hours)
	return datetime.combine(study_today(now), datetime.min.time(), tzinfo=timezone.utc) - offset


async def weekly_xp(db: AsyncSession, user_ids: list[uuid.UUID], now: datetime | None = None) -> dict[uuid.UUID, int]:
	"""XP tuần này của từng user, tính từ activity_log (chỉ gồm hoạt động từ khi có bảng này)."""
	rows = await db.execute(
		select(ActivityLog.user_id, func.sum(ActivityLog.xp))
		.where(ActivityLog.user_id.in_(user_ids), ActivityLog.created_at >= week_start(now))
		.group_by(ActivityLog.user_id)
	)
	return {uid: int(xp) for uid, xp in rows.all()}


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


def missed_days(current: int, last_active: date | None, today: date) -> int:
	"""Số ngày trọn vẹn bị bỏ lỡ giữa lần học cuối và hôm nay (0 nếu chưa có chuỗi)."""
	if current <= 0 or last_active is None or today <= last_active:
		return 0
	return (today - last_active).days - 1


def visible_streak(current: int, last_active: date | None, today: date, freezes: int = 0) -> int:
	"""Streak hiển thị: chuỗi còn sống nếu học hôm qua hoặc hôm nay (hoặc freeze đủ lấp các ngày
	bỏ lỡ), ngược lại đã đứt (0)."""
	if last_active is not None and last_active >= today - timedelta(days=1 + freezes):
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
	duration_seconds: int | None = None,
	xp: int | None = None,
) -> None:
	"""Cộng XP và cập nhật streak; nếu hoạt động thuộc 1 kỹ năng và có `score` (thang 0-100) thì
	cập nhật luôn skill_progress. KHÔNG commit — gọi cùng transaction với việc lưu kết quả
	hoạt động để hoặc cả hai cùng được ghi, hoặc cả hai cùng bị huỷ.

	`duration_seconds`: CHỈ có giá trị khi client đang bật "chế độ bấm giờ" (users.timer_mode_enabled)
	và tự đo được — không tự suy diễn/mặc định ở đây. Ghi 1 dòng study_time_log khi > 0 để tính
	"phút học trong tuần" theo kỹ năng (GET /api/activity/weekly-summary).
	"""
	if xp is None:
		xp = XP_BY_ACTIVITY[activity]
	db.add(ActivityLog(user_id=user_id, activity=activity, xp=xp))
	if score is not None and activity in SKILL_BY_ACTIVITY:
		await record_skill_score(db, user_id, SKILL_BY_ACTIVITY[activity], score, cefr_level)
	if duration_seconds and duration_seconds > 0 and activity in SKILL_BY_ACTIVITY:
		db.add(StudyTimeLog(user_id=user_id, skill=SKILL_BY_ACTIVITY[activity], duration_seconds=duration_seconds))
	today = study_today(now)

	# Tạo dòng nếu user chưa có (ON CONFLICT tránh lỗi khi 2 request đầu tiên chạy song song),
	# rồi khoá dòng để hai hoạt động đồng thời không cộng đè lên nhau.
	await db.execute(pg_insert(Streak).values(user_id=user_id).on_conflict_do_nothing(index_elements=["user_id"]))
	streak = await db.scalar(select(Streak).where(Streak.user_id == user_id).with_for_update())

	# Chuỗi >= MIN_RESTORABLE_STREAK vừa đứt (hôm nay là ngày học đầu tiên sau khi đứt) -> nhớ lại để
	# user khôi phục bằng quiz trong ngày (restore_streak).
	previous = streak.current_streak or 0
	freezes = streak.freezes_available or 0
	if previous >= MIN_RESTORABLE_STREAK and visible_streak(previous, streak.last_active_date, today, freezes) == 0:
		streak.lost_streak, streak.lost_on = previous, today
	last_active = streak.last_active_date
	missed = missed_days(previous, last_active, today)
	if 0 < missed <= freezes:
		# Freeze tự động lấp các ngày bỏ lỡ: coi như hôm qua vẫn có học.
		freezes -= missed
		last_active = today - timedelta(days=1)
	streak.current_streak = next_streak(previous, last_active, today)
	if streak.current_streak != previous and streak.current_streak % FREEZE_EVERY_DAYS == 0:
		freezes = min(freezes + 1, MAX_FREEZES)
	streak.freezes_available = freezes
	streak.longest_streak = max(streak.longest_streak or 0, streak.current_streak)
	streak.last_active_date = today
	streak.total_xp = (streak.total_xp or 0) + xp


async def restore_streak(
	db: AsyncSession, user_id: uuid.UUID, num_questions: int, score: float, now: datetime | None = None
) -> bool:
	"""Gọi sau khi chấm quiz (KHÔNG commit): quiz đủ dài + đạt điểm thì lấy lại chuỗi vừa đứt, tính
	cả hôm nay. Chỉ hiệu lực trong đúng ngày phát hiện đứt và chỉ 1 lần. Trả True nếu đã khôi phục."""
	if num_questions < RESTORE_MIN_QUESTIONS or score < RESTORE_MIN_SCORE:
		return False
	streak = await db.scalar(select(Streak).where(Streak.user_id == user_id).with_for_update())
	if streak is None or not streak.lost_streak or streak.lost_on != study_today(now):
		return False
	streak.current_streak = streak.lost_streak + 1
	streak.longest_streak = max(streak.longest_streak or 0, streak.current_streak)
	streak.lost_streak, streak.lost_on = 0, None
	return True


async def get_summary(db: AsyncSession, user_id: uuid.UUID, now: datetime | None = None) -> dict:
	"""Số liệu cho GET /api/streaks; user chưa học lần nào trả toàn số 0 (không tạo dòng mới)."""
	today = study_today(now)
	streak = await db.scalar(select(Streak).where(Streak.user_id == user_id))

	total_xp = (streak.total_xp or 0) if streak else 0
	last_active = streak.last_active_date if streak else None
	freezes = (streak.freezes_available or 0) if streak else 0
	current = visible_streak(streak.current_streak or 0, last_active, today, freezes) if streak else 0
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
		"restorable_streak": _restorable(streak, current, today) if streak else 0,
		"freezes_available": freezes,
	}


def _restorable(streak: Streak, visible: int, today: date) -> int:
	# Đã đứt nhưng chưa có hoạt động nào hôm nay -> chuỗi cũ; đã học lại hôm nay -> lost_streak.
	if visible == 0 and (streak.current_streak or 0) >= MIN_RESTORABLE_STREAK:
		return streak.current_streak
	return streak.lost_streak or 0 if streak.lost_on == today else 0


async def get_weekly_activity(db: AsyncSession, user_id: uuid.UUID, now: datetime | None = None) -> dict:
	"""Tổng phút học 7 ngày gần nhất theo kỹ năng, cho GET /api/activity/weekly-summary.

	Chỉ tổng hợp study_time_log — bảng này chỉ có dòng khi user đã bật timer mode lúc hoạt động
	đó diễn ra, nên user chưa từng bật timer mode sẽ luôn ra toàn số 0 (không phải lỗi thiếu dữ
	liệu, đúng ý nghĩa "chưa đo gì cả").
	"""
	since = (now or datetime.now(timezone.utc)) - timedelta(days=7)
	rows = (
		await db.execute(
			select(StudyTimeLog.skill, func.sum(StudyTimeLog.duration_seconds))
			.where(StudyTimeLog.user_id == user_id, StudyTimeLog.created_at >= since)
			.group_by(StudyTimeLog.skill)
		)
	).all()
	seconds_by_skill = {skill: 0 for skill in SKILL_BY_ACTIVITY.values()}
	for skill, total_seconds in rows:
		seconds_by_skill[skill] = int(total_seconds)
	minutes_by_skill = {skill: round(seconds / 60) for skill, seconds in seconds_by_skill.items()}
	return {
		"minutes_by_skill": minutes_by_skill,
		"total_minutes": sum(minutes_by_skill.values()),
	}
