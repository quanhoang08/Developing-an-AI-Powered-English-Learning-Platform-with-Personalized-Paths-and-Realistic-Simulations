from datetime import date, datetime

from pydantic import BaseModel


class StreakResponse(BaseModel):
	"""GET /api/streaks: 3 field đầu theo api-spec mục 7, phần còn lại phục vụ UI XP/level và lưới streak."""

	current_streak: int
	longest_streak: int
	last_active_date: date | None
	today_active: bool
	total_xp: int
	level: int
	xp_into_level: int
	xp_for_next_level: int
	# Các ngày thuộc chuỗi hiện tại (ISO), không phải toàn bộ lịch sử học — bảng streaks chỉ
	# lưu last_active_date + độ dài chuỗi, không lưu từng ngày.
	recent_active_dates: list[date]
	# >0: chuỗi vừa đứt, làm quiz >=10 câu đạt >=70% trong ngày để lấy lại (+1 cho hôm nay).
	restorable_streak: int = 0
	# Freeze còn lại: mỗi 7 ngày liên tiếp được tặng 1 (tối đa 2), tự dùng khi bỏ lỡ ngày.
	freezes_available: int = 0


class SkillProgressResponse(BaseModel):
	"""1 phần tử của GET /api/skills: điểm trung bình động 0-100, cefr_level chỉ có với writing."""

	skill_name: str
	score: float | None
	cefr_level: str | None
	updated_at: datetime | None


class WeeklyActivityResponse(BaseModel):
	"""GET /api/activity/weekly-summary: phút học 7 ngày gần nhất theo kỹ năng.

	timer_mode_enabled cho frontend biết có nên hiển thị số thật hay lời mời bật bấm giờ — số
	trong minutes_by_skill luôn là 0 khi timer_mode_enabled=false (chưa từng đo).
	"""

	timer_mode_enabled: bool
	minutes_by_skill: dict[str, int]
	total_minutes: int


class RecentActivityItem(BaseModel):
	"""1 phần tử của GET /api/activity/recent — 1 lượt học gần nhất, bất kể kỹ năng nào."""

	skill: str
	title: str
	# 0-100 khi hoạt động đó có điểm số thật (reading/dictation/writing); None với speaking (chưa
	# có điểm tổng theo phiên, chỉ có điểm từng lượt nói) — frontend ẩn progress bar khi None.
	score: float | None
	created_at: datetime
