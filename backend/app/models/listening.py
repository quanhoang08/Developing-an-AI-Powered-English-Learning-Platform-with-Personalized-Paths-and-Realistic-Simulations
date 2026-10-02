# Models Module 2 — Listening. Cột khớp bảng thật trong Postgres (kiểm tra trực tiếp bằng
# \d, KHÔNG theo docs/schema.sql — root schema.sql cũ hơn mới là bản Docker thật sự dùng để
# khởi tạo volume; docs/schema.sql là thiết kế mục tiêu, một phần đã lệch so với DB đang chạy,
# xem migration 20260917_0008 để biết các cột nào được ALTER thêm cho khớp feature-listening.md).
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Persona(Base):
	"""Giọng đọc dùng chung Podcast/Speaking/Movie Context — cột đã có sẵn trong DB thật."""

	__tablename__ = "personas"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	name: Mapped[str] = mapped_column(String(100))
	provider: Mapped[str] = mapped_column(String(30))
	voice_id: Mapped[str] = mapped_column(String(100))
	accent_tag: Mapped[str] = mapped_column(String(30), nullable=True)
	description: Mapped[str] = mapped_column(Text, nullable=True)
	# is_active/created_at: thêm ở migration 0008 (bản gốc chưa có) — cần cho business rule
	# "persona không active → fallback persona mặc định" (feature-listening.md mục 1.5).
	is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default=text("now()"))


class Podcast(Base):
	"""1 podcast sinh từ 1 document — audio gốc (nếu document là audio) hoặc TTS (nếu .docx)."""

	__tablename__ = "podcasts"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	document_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE")
	)
	# script_text: văn bản đã biên tập lại cho văn nói trước khi TTS (.docx), hoặc transcript
	# STT thô (audio gốc) — luôn có, kể cả trước khi audio_url sẵn sàng.
	script_text: Mapped[str] = mapped_column(Text)
	audio_url: Mapped[str] = mapped_column(Text, nullable=True)
	duration_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
	# persona_id: thêm ở migration 0008, thay cho persona_ids[] cũ (spec chỉ chọn 1 giọng đọc
	# cho mỗi podcast — feature-listening.md mục 1.2 "persona_id (tuỳ chọn)", số ít).
	persona_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True
	)
	# status: thêm ở migration 0008 — theo dõi processing/ready/failed giống documents.status.
	status: Mapped[str] = mapped_column(String(20), server_default=text("'processing'"))
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default=text("now()"))


class TranscriptSegment(Base):
	"""1 từ trong transcript của podcast, kèm timestamp — đơn vị đồng bộ cấp TỪ theo đúng
	business rule mục 2.4 (không phải cấp câu). Cột word_index/word_text/start_time_ms/
	end_time_ms đã có sẵn trong DB thật, khớp đúng ý định thiết kế — giữ nguyên tên cột,
	không đổi sang text/start_ms/end_ms như docs/schema.sql (bảo thủ về schema)."""

	__tablename__ = "transcript_segments"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	podcast_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("podcasts.id", ondelete="CASCADE")
	)
	word_index: Mapped[int] = mapped_column(Integer)
	word_text: Mapped[str] = mapped_column(String(100))
	start_time_ms: Mapped[int] = mapped_column(Integer)
	end_time_ms: Mapped[int] = mapped_column(Integer)


class DictationAttempt(Base):
	"""1 lượt Dictation — nghe 1 đoạn ~15-30s trích từ podcast, gõ lại, chấm lỗi cấp từ.

	start_word_index/end_word_index (thêm ở migration 0008): đoạn transcript_segments được
	chọn cho attempt này, dùng lại thay vì start_ms/end_ms vì transcript đã có sẵn word_index
	liên tục — tránh phải tra ngược từ mốc thời gian sang từ mỗi lần chấm.
	"""

	__tablename__ = "dictation_attempts"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	podcast_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("podcasts.id", ondelete="CASCADE")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	start_word_index: Mapped[int] = mapped_column(Integer)
	end_word_index: Mapped[int] = mapped_column(Integer)
	# audio_segment_path: file audio đã cắt riêng cho đoạn này, trả về client nghe (KHÔNG
	# trả text gốc — feature-listening.md mục 3.3 bước 2).
	audio_segment_path: Mapped[str] = mapped_column(Text, nullable=True)
	# reference_word_tags: gắn nhãn hiếm/tên riêng cho từng từ trong đoạn NGAY LÚC TẠO attempt
	# (feature-listening.md mục 3.5, bước 1) — dùng lại khi chấm ở bước submit, không tính lại.
	reference_word_tags: Mapped[list[dict]] = mapped_column(
		JSONB, server_default=text("'[]'::jsonb")
	)
	# NOT NULL trong DB thật (kế thừa từ schema gốc) — cùng convention rỗng-nghĩa-là-chưa-nộp
	# như WritingSubmission.submitted_text, không dùng NULL cho "chưa nộp bài".
	user_input_text: Mapped[str] = mapped_column(Text, server_default=text("''"))
	# diff_result: toàn bộ danh sách lỗi (missing/extra/wrong) đã chấm, lưu lại để lần GET
	# sau (hoặc resubmit) không phải chấm lại — cùng nguyên tắc idempotent như Writing/Reading.
	diff_result: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
	accuracy_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default=text("now()"))


class ListeningQuizAttempt(Base):
	"""1 quiz nghe hiểu sinh từ transcript podcast (migration 20261002_0024). `questions` giữ cả
	correct_index/trap_note/mốc căn cứ lúc sinh; `picks` + điểm chỉ có sau khi nộp."""

	__tablename__ = "listening_quiz_attempts"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
	podcast_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("podcasts.id", ondelete="CASCADE")
	)
	questions: Mapped[list] = mapped_column(JSONB)
	picks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
	correct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
	score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
	submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
