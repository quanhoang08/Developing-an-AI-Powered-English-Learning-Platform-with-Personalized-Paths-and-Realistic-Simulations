from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

SourceType = Literal["document_summary", "extended_topic", "free_topic"]
CertificateStyle = Literal["toeic", "ielts", "cambridge"]


class SubmissionCreate(BaseModel):
	"""Payload tạo writing_submissions; ràng buộc document_id theo source_type."""

	source_type: SourceType
	document_id: str | None = None
	# Bắt buộc khi source_type=free_topic và người học tự nhập đề (không xin gợi ý AI).
	prompt_text: str | None = Field(default=None, max_length=2000)
	certificate_style: CertificateStyle | None = None

	@model_validator(mode="after")
	def check_source_constraints(self) -> "SubmissionCreate":
		# document_summary/extended_topic cần document_id hợp lệ; free_topic thì không dùng document.
		if self.source_type in {"document_summary", "extended_topic"} and not self.document_id:
			raise ValueError("document_id_required_for_source_type")
		if self.source_type == "free_topic":
			if self.document_id:
				raise ValueError("document_id_not_allowed_for_free_topic")
			# POST /submissions luôn cần prompt_text có sẵn (tự nhập, hoặc lấy từ 1 trong
			# prompt_options mà POST /prompts/suggest trả về ở bước trước — xem PromptSuggestRequest).
			if not self.prompt_text:
				raise ValueError("free_topic_requires_prompt_text")
		return self


class SubmissionResponse(BaseModel):
	# Trả về sau khi tạo submission; prompt_text là đề bài cuối cùng (tự nhập hoặc AI sinh).
	submission_id: str
	source_type: SourceType
	prompt_text: str


class InsightResponse(BaseModel):
	# 1 gợi ý/lỗi Gemini phát hiện trong bài viết (grammar/vocabulary/style).
	insight_type: str
	title: str
	description: str
	original_text: str | None = None
	suggested_text: str | None = None


class SubmitEssayRequest(BaseModel):
	# Nội dung bài luận thật người học nộp để chấm điểm.
	submitted_text: str = Field(min_length=1, max_length=20000)
	# Chỉ gửi khi client đang bật "chế độ bấm giờ" (mục 3.16 lumina_context.md).
	duration_seconds: int | None = Field(default=None, gt=0)


class RubricScores(BaseModel):
	# 4 tiêu chí kiểu IELTS Writing Task 2, thang 0-100 — chỉ dùng cho extended_topic/free_topic.
	task_response: int
	coherence_cohesion: int
	lexical_resource: int
	grammatical_range_accuracy: int


class SubmitEssayResponse(BaseModel):
	# Kết quả chấm trả về ngay sau khi nộp bài.
	score: float
	cefr_level: str
	ielts_band: str
	source_type: SourceType
	rubric_scores: RubricScores | None
	insights: list[InsightResponse]


class WritingSubmissionDetail(BaseModel):
	# Toàn bộ thông tin 1 submission, dùng cho GET chi tiết.
	id: str
	source_type: SourceType
	prompt_text: str | None
	document_id: str | None
	certificate_style: str | None
	submitted_text: str
	overall_score: float | None
	cefr_level: str | None
	ielts_band: str | None
	rubric_scores: RubricScores | None
	created_at: datetime
	completed_at: datetime | None


class PromptSuggestRequest(BaseModel):
	"""Bước chọn đề TRƯỚC khi tạo submission — xem feature-writing.md mục 1.1-1.2."""

	source_type: SourceType
	document_id: str | None = None
	# Chỉ dùng khi free_topic và người học tự nhập đề (không xin gợi ý AI).
	topic: str | None = Field(default=None, min_length=1, max_length=200)
	# Chỉ dùng khi free_topic và xin gợi ý theo phong cách chứng chỉ (không kèm topic).
	certificate_style: CertificateStyle | None = None
	level: str | None = Field(default=None, min_length=2, max_length=2)

	@model_validator(mode="after")
	def check_constraints(self) -> "PromptSuggestRequest":
		if self.source_type in {"document_summary", "extended_topic"} and not self.document_id:
			raise ValueError("document_id_required_for_source_type")
		if self.source_type == "free_topic":
			if self.document_id:
				raise ValueError("document_id_not_allowed_for_free_topic")
			if bool(self.topic) == bool(self.certificate_style):
				raise ValueError("exactly_one_of_topic_or_certificate_style_required")
		return self


class PromptSuggestResponse(BaseModel):
	# Đúng 1 trong 2: prompt_text (đề đã chốt) hoặc prompt_options (chờ người học chọn 1).
	prompt_text: str | None = None
	source_type: SourceType | None = None
	prompt_options: list[str] | None = None


class GrammarCheckRequest(BaseModel):
	"""Đúng 1 trong 2: submission_id (chấm bài đã có, có lưu) hoặc raw_text (preview, không lưu)."""

	submission_id: str | None = None
	raw_text: str | None = Field(default=None, max_length=20000)

	@model_validator(mode="after")
	def check_exactly_one(self) -> "GrammarCheckRequest":
		if bool(self.submission_id) == bool(self.raw_text):
			raise ValueError("exactly_one_of_submission_id_or_raw_text_required")
		return self


class GrammarInsight(BaseModel):
	# offset tính theo ký tự (UTF-8 code point) trên text gốc — client highlight đúng vị trí.
	insight_type: str = "grammar"
	offset_start: int
	offset_end: int
	original_text: str
	suggested_text: str
	explanation: str


class GrammarCheckResponse(BaseModel):
	insights: list[GrammarInsight]


class RephraseCreate(BaseModel):
	# sentence_text rỗng → hệ thống tự chọn câu yếu nhất trong bài để gợi ý viết lại.
	submission_id: str
	sentence_text: str | None = Field(default=None, max_length=1000)


class RephraseSuggestion(BaseModel):
	text: str
	explanation: str


class RephraseResponse(BaseModel):
	original_sentence: str
	suggested_sentences: list[RephraseSuggestion]
