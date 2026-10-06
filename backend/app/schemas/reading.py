from typing import Literal

from pydantic import BaseModel, Field, model_validator


class LookupRequest(BaseModel):
	"""Từ và câu chứa từ để định nghĩa theo ngữ cảnh."""

	term: str = Field(min_length=1, max_length=100)
	context_sentence: str = Field(min_length=1, max_length=5000)
	source_document_id: str | None = None
	source_url: str | None = None


class LookupSense(BaseModel):
	"""1 nghĩa của từ (kiểu Cambridge): loại từ, level CEFR, nghĩa tiếng Việt, ví dụ."""

	part_of_speech: str
	level: str
	meaning_vi: str
	example_en: str


class LookupResponse(BaseModel):
	"""Response ổn định cho Reading UI và bước lưu vocabulary."""

	definition: str
	synonyms: list[str]
	antonyms: list[str]
	example_sentence: str
	ipa: str | None = None
	senses: list[LookupSense] = []


class ClassicSessionCreate(BaseModel):
	"""Payload tạo Classic Reading session."""

	document_id: str
	num_questions: int = Field(default=5, ge=3, le=15)
	difficulty: str | None = Field(default=None, min_length=2, max_length=2)


class ReadingQuestion(BaseModel):
	"""Question public; correct option không được trả trước submit."""

	id: str
	question_text: str
	options: list[str]


class ClassicSessionResponse(BaseModel):
	# Trả về sau khi tạo session; danh sách câu hỏi không kèm đáp án đúng.
	session_id: str
	questions: list[ReadingQuestion]


class ReadingAnswerSubmit(BaseModel):
	# 1 lựa chọn của người học cho 1 câu hỏi cụ thể trong session.
	question_id: str
	selected_option_index: int = Field(ge=0, le=3)


class ReadingSubmitRequest(BaseModel):
	# Nộp toàn bộ đáp án của 1 session (Classic hoặc Skim & Scan) để chấm điểm.
	answers: list[ReadingAnswerSubmit]
	# Chỉ gửi khi client đang bật "chế độ bấm giờ" (mục 3.16 lumina_context.md) — thiếu field này
	# hoàn toàn bình thường, không ghi study_time_log.
	duration_seconds: int | None = Field(default=None, gt=0)


class ReadingResult(BaseModel):
	# Kết quả chấm của 1 câu hỏi, trả về sau khi nộp — giờ mới lộ đáp án đúng + trích dẫn.
	question_id: str
	correct_option_index: int
	source_chunk_id: str | None
	explanation: str | None = None


class ReadingSubmitResponse(BaseModel):
	score: float
	results: list[ReadingResult]


class SkimScanSessionCreate(BaseModel):
	"""Đúng 1 trong 2: document_id (passage thật từ tài liệu) hoặc topic (AI tự sinh)."""

	level: str = Field(min_length=2, max_length=2)
	document_id: str | None = None
	topic: str | None = Field(default=None, min_length=1, max_length=100)
	time_limit_seconds: int = Field(default=90, ge=30, le=600)
	question_type: Literal["multiple_choice", "tfng"] = "multiple_choice"

	@model_validator(mode="after")
	def check_exactly_one_source(self) -> "SkimScanSessionCreate":
		if bool(self.document_id) == bool(self.topic):
			raise ValueError("exactly_one_of_document_id_or_topic_required")
		return self


class SkimScanSessionResponse(BaseModel):
	# source_document_id khác None nghĩa là content trích thật từ tài liệu, không phải AI sinh.
	session_id: str
	passage_id: str
	title: str | None
	content: str
	source_document_id: str | None
	questions: list[ReadingQuestion]
	time_limit_seconds: int


class GuessContextCreate(BaseModel):
	"""Contextual Guessing: chọn từ đã lưu (vocab_item_id) hoặc gõ từ tự do (term) — ít nhất 1."""

	vocab_item_id: str | None = None
	term: str | None = Field(default=None, min_length=1, max_length=100)

	@model_validator(mode="after")
	def check_at_least_one(self) -> "GuessContextCreate":
		if not self.vocab_item_id and not self.term:
			raise ValueError("vocab_item_id_or_term_required")
		return self


class GuessContextResponse(BaseModel):
	# Không có correct_option_index: đáp án chỉ lộ sau khi submit.
	attempt_id: str
	challenge_sentence: str
	options: list[str]


class GuessContextSubmit(BaseModel):
	selected_option_index: int = Field(ge=0, le=3)


class GuessContextSubmitResponse(BaseModel):
	correct: bool
	correct_option_index: int


class StoryCreate(BaseModel):
	vocab_item_ids: list[str] = Field(min_length=1, max_length=15)
	theme: str | None = Field(default=None, max_length=100)
	length: str = Field(default="medium", pattern="^(short|medium|long)$")


class AdaptTextRequest(BaseModel):
	text: str = Field(min_length=20, max_length=1500)
	level: Literal["A2", "B1", "B2", "C1"] = "B1"


class AdaptedSentence(BaseModel):
	en: str
	vi: str


class AdaptTextResponse(BaseModel):
	level: str
	sentences: list[AdaptedSentence]


class StoryResponse(BaseModel):
	# missing_terms: từ user chọn nhưng model không dùng trong truyện — UI báo để user tự xử lý.
	id: str
	content: str
	missing_terms: list[str]
