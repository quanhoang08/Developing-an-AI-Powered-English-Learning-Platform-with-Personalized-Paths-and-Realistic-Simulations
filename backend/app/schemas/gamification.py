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


class SkillProgressResponse(BaseModel):
	"""1 phần tử của GET /api/skills: điểm trung bình động 0-100, cefr_level chỉ có với writing."""

	skill_name: str
	score: float | None
	cefr_level: str | None
	updated_at: datetime | None
