from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserErrorResponse(BaseModel):
	id: UUID
	error_type: str
	spaced_repetition_level: int
	detail: dict | None
	created_at: datetime | None
	priority_score: float


class ReviewQueueItem(BaseModel):
	# item_type: 'vocab' (item_id = vocab_items.id) hoặc 'error' (item_id = user_errors.id).
	item_type: str
	item_id: UUID
	priority_score: float
	label: str | None


class QuizGenerateRequest(BaseModel):
	focus_error_types: list[str] | None = None
	num_questions: int = Field(default=5, ge=1, le=15)


class QuizQuestionPublic(BaseModel):
	question_text: str
	options: list[str]
	error_type: str


class QuizResponse(BaseModel):
	quiz_id: UUID
	questions: list[QuizQuestionPublic]


class QuizAttemptRequest(BaseModel):
	# answers[i] = chỉ số đáp án đã chọn cho câu hỏi thứ i.
	answers: list[int]


class QuizQuestionResult(BaseModel):
	is_correct: bool
	correct_option_index: int
	explanation: str


class QuizAttemptResponse(BaseModel):
	attempt_id: UUID
	score: float
	results: list[QuizQuestionResult]
	streak_restored: bool = False


class HabitsResponse(BaseModel):
	window_days: int
	active_days: int
	activities_per_active_day: float
	studied_today: bool
	peak_hour: int | None
	activity_by_skill: dict[str, int]
	preferred_skill: str | None
	quiz_score_change: float | None
	progress_trend: str
