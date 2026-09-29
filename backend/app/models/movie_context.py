# Models Movie Delivery Context — nhánh TTS fallback (Thử nghiệm giới hạn). Cột khớp root schema.sql.
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MovieContextTtsFallback(Base):
	"""1 câu ví dụ + audio đọc mẫu, dùng chung giữa các user (cache theo phrase_text + persona)."""

	__tablename__ = "movie_context_tts_fallback"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	phrase_text: Mapped[str] = mapped_column(Text)
	persona_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("personas.id"), nullable=True
	)
	# Đường dẫn file WAV trên đĩa server (giống podcasts.audio_url), client nghe qua endpoint audio.
	audio_url: Mapped[str] = mapped_column(Text)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default=text("now()"))


class VideoSource(Base):
	"""1 video có phụ đề. video_url là TÊN FILE trong storage_video_dir (không phải đường dẫn tuyệt đối)."""

	__tablename__ = "video_sources"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	title: Mapped[str] = mapped_column(String(255), nullable=True)
	platform: Mapped[str] = mapped_column(String(30), nullable=True)
	video_url: Mapped[str] = mapped_column(Text)
	subtitle_language: Mapped[str] = mapped_column(String(10), server_default=text("'en'"))


class VideoSubtitleIndex(Base):
	"""1 dòng phụ đề + mốc thời gian; có GIN index full-text tiếng Anh trên phrase_text."""

	__tablename__ = "video_subtitle_index"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	video_source_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("video_sources.id", ondelete="CASCADE")
	)
	phrase_text: Mapped[str] = mapped_column(Text)
	start_time_ms: Mapped[int] = mapped_column(Integer)
	end_time_ms: Mapped[int] = mapped_column(Integer)


class MovieContextMatch(Base):
	"""Kết quả 1 lần tìm của user: tts_fallback (tts_fallback_id) HOẶC real_video (video_subtitle_index_id)."""

	__tablename__ = "movie_context_matches"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
	search_phrase: Mapped[str] = mapped_column(String(255))
	source_type: Mapped[str] = mapped_column(String(20))
	video_subtitle_index_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("video_subtitle_index.id"), nullable=True
	)
	tts_fallback_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("movie_context_tts_fallback.id"), nullable=True
	)
	is_saved: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default=text("now()"))
