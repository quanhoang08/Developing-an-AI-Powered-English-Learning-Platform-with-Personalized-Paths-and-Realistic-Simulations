from typing import Literal

from pydantic import BaseModel, Field


class ToeicPracticeRequest(BaseModel):
	part: Literal[1, 2, 3, 4, 5, 6, 7]
	count: int = Field(8, ge=3, le=10)  # chỉ Part 2/5; Part 3/4/6/7 luôn 3 câu theo 1 bài


class ToeicQuestion(BaseModel):
	prompt: str
	passage: str | None = None
	options: list[str]
	image: str | None = None  # Part 1: tên file ảnh, tải qua GET /api/toeic/part1/images/{name}
	credit: str | None = None  # Part 1: ghi công tác giả/giấy phép ảnh
	part: int | None = None  # chỉ đề thi thử: câu thuộc Part nào
	group: int | None = None  # chỉ đề thi thử: các câu cùng bài (Part 3/4/6/7) có cùng group


class ToeicPracticeResponse(BaseModel):
	attempt_id: str
	part: int
	time_limit_seconds: int
	questions: list[ToeicQuestion]


class ToeicSubmitRequest(BaseModel):
	picks: list[int | None] = Field(max_length=250)  # đề thi thử có tới ~190 câu
	duration_seconds: int | None = Field(None, ge=0, le=7200)


class ToeicResult(BaseModel):
	chosen: int | None
	correct_index: int
	is_correct: bool
	explanation_vi: str
	contrast_vi: str | None = None


class ToeicSubmitResponse(BaseModel):
	score: float
	correct_count: int
	total: int
	results: list[ToeicResult]
	# Chỉ đề thi thử: đúng/tổng từng Part và điểm ước lượng thô /990 từ chính bài này.
	by_part: list[dict] | None = None
	estimate: dict | None = None


class ToeicPartStat(BaseModel):
	part: int
	attempts: int
	questions: int
	accuracy: float


class ToeicEstimate(BaseModel):
	listening: int | None
	reading: int | None
	total: int | None
	note: str


class ToeicSummary(BaseModel):
	parts: list[ToeicPartStat]
	estimate: ToeicEstimate
