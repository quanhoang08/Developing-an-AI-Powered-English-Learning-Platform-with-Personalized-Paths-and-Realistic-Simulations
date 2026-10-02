from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class VocabCreate(BaseModel):
	"""Payload lưu từ; phải có đúng một nguồn document hoặc URL."""

	term: str = Field(min_length=1, max_length=100)
	definition: str | None = None
	document_id: UUID | None = None
	source_url: str | None = None
	ipa: str | None = None
	part_of_speech: str | None = None
	example_sentence: str | None = None
	synonyms: list[str] = []
	antonyms: list[str] = []

	@model_validator(mode="after")
	def validate_source(self):
		if (self.document_id is None) == (self.source_url is None):
			raise ValueError("exactly_one_source_required")
		return self


class VocabResponse(BaseModel):
	# DTO trả về sau khi tạo/liệt kê từ vựng.
	id: UUID
	term: str
	definition: str | None
	document_id: UUID | None
	source_url: str | None
	ipa: str | None
	part_of_speech: str | None
	example_sentence: str | None
	synonyms: list[str] | None
	antonyms: list[str] | None
	created_at: datetime


class VocabReviewRequest(BaseModel):
	# quality: người học tự chấm mức độ nhớ (0=quên hẳn, 5=nhớ hoàn hảo) — input cho SM-2.
	quality: int = Field(ge=0, le=5)


class VocabReviewResponse(BaseModel):
	# Lịch ôn tập tiếp theo do sm2_service tính ra sau khi ghi nhận review này.
	next_review_at: datetime
	ease_factor: float


class VocabSentenceRequest(BaseModel):
	# Câu người học tự đặt với từ; giới hạn độ dài để chặn prompt quá lớn.
	sentence: str = Field(min_length=3, max_length=300)


class WordFamilyEntry(BaseModel):
	word: str
	part_of_speech: str


class WordFamilyResponse(BaseModel):
	word_family: list[WordFamilyEntry]
	collocations: list[str]


class VocabSentenceResponse(BaseModel):
	meaning_fits: bool
	grammar_ok: bool
	corrected_sentence: str
	feedback_vi: str
