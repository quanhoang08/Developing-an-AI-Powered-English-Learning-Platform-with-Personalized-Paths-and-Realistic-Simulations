from pydantic import BaseModel


class MovieContextMatchItem(BaseModel):
	match_id: str
	source_type: str  # "real_video" | "tts_fallback"
	phrase_text: str
	is_saved: bool
	# tts_fallback: chỉ có audio_url. real_video: video_url + title + mốc thời gian dòng phụ đề khớp.
	audio_url: str | None = None
	video_url: str | None = None
	title: str | None = None
	platform: str | None = None  # "demo" = cảnh mô phỏng; khác = phim thật
	start_ms: int | None = None
	end_ms: int | None = None


class SubtitleCue(BaseModel):
	text: str
	start_ms: int
	end_ms: int
	is_match: bool  # dòng chứa cụm từ người học tìm


class MovieContextSearchResponse(BaseModel):
	matches: list[MovieContextMatchItem]
