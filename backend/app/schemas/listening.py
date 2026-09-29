from typing import Literal

from pydantic import BaseModel, Field


class DictationSegmentRange(BaseModel):
	"""Đoạn cụ thể người học muốn luyện, tính bằng mili giây trên trục thời gian podcast."""

	start_ms: int = Field(ge=0)
	end_ms: int = Field(gt=0)


class DictationCreateRequest(BaseModel):
	# segment_range=None -> service tự chọn ~20s đầu tiên (feature-listening.md mục 3.2).
	podcast_id: str
	segment_range: DictationSegmentRange | None = None


class DictationCreateResponse(BaseModel):
	# Cố ý KHÔNG trả text gốc — người học phải tự nghe để chép lại (mục 3.3 bước 2).
	attempt_id: str
	audio_url: str


class DictationSubmitRequest(BaseModel):
	# Cho phép rỗng — "bỏ trống hoàn toàn" là 1 edge case hợp lệ, không phải lỗi validate (mục 3.5).
	transcribed_text: str = Field(max_length=5000)
	# Chỉ gửi khi client đang bật "chế độ bấm giờ" (mục 3.16 lumina_context.md).
	duration_seconds: int | None = Field(default=None, gt=0)


class DictationErrorItem(BaseModel):
	type: Literal["missing", "extra", "wrong"]
	word: str
	position: int


class DictationSubmitResponse(BaseModel):
	score: float
	errors: list[DictationErrorItem]


class PodcastCreateRequest(BaseModel):
	document_id: str
	persona_id: str | None = None


class PodcastResponse(BaseModel):
	id: str
	status: str
	audio_url: str | None = None
	persona_id: str | None = None
	duration_seconds: int | None = None


class PodcastListItem(BaseModel):
	id: str
	title: str
	status: str
	duration_seconds: int | None = None
	source_type: str | None = None


class TranscriptWordItem(BaseModel):
	# Đơn vị cấp TỪ (mục 2.4) — tên trường theo api-spec: text/start_ms/end_ms.
	text: str
	start_ms: int
	end_ms: int


class TranscriptResponse(BaseModel):
	segments: list[TranscriptWordItem]
