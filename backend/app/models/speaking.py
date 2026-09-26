# Models Module 4 — Speaking. Cột khớp bảng thật trong Postgres (schema.sql gốc + migration
# 20260919_0009 cho các cột bổ sung theo feature-speaking.md mục 1.4 / 3.3).
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Scenario(Base):
	"""Kịch bản hội thoại mô phỏng; goal/formality_level là ground-truth chấm ý định/lịch sự."""

	__tablename__ = "scenarios"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	title: Mapped[str] = mapped_column(String(150))
	description: Mapped[str] = mapped_column(Text, nullable=True)
	difficulty_level: Mapped[str] = mapped_column(String(10), nullable=True)
	target_intents: Mapped[list] = mapped_column(JSONB, nullable=True)
	goal: Mapped[str] = mapped_column(Text, nullable=True)
	formality_level: Mapped[str] = mapped_column(String(20), server_default=text("'neutral'"))


class ConversationSession(Base):
	"""1 phiên hội thoại gắn đúng 1 scenario suốt vòng đời (mục 1.4)."""

	__tablename__ = "conversation_sessions"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	scenario_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("scenarios.id"), nullable=True
	)
	persona_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("personas.id"), nullable=True
	)
	status: Mapped[str] = mapped_column(String(20), server_default=text("'in_progress'"))
	started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default=text("now()"))
	ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationTurn(Base):
	"""1 lượt hợp lệ: STT + phát âm + ý định/lịch sự + phản hồi AI (mục 1.3-1.6)."""

	__tablename__ = "conversation_turns"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	conversation_session_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("conversation_sessions.id", ondelete="CASCADE")
	)
	turn_index: Mapped[int] = mapped_column(Integer)
	user_audio_url: Mapped[str] = mapped_column(Text, nullable=True)
	user_transcript: Mapped[str] = mapped_column(Text, nullable=True)
	pronunciation_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
	pronunciation_advice: Mapped[str] = mapped_column(Text, nullable=True)
	# NULL (không áng chừng) khi LLM trả sai schema — mục 3.3, tránh làm lệch Adaptive Engine.
	intent_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
	politeness_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
	ai_response_text: Mapped[str] = mapped_column(Text, nullable=True)
	ai_response_audio_url: Mapped[str] = mapped_column(Text, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default=text("now()"))
	stt_provider_used: Mapped[str] = mapped_column(String(20), nullable=True)
	pronunciation_assessment_failed: Mapped[bool] = mapped_column(
		Boolean, server_default=text("false")
	)
	intent_feedback: Mapped[str] = mapped_column(Text, nullable=True)
	politeness_feedback: Mapped[str] = mapped_column(Text, nullable=True)
	suggested_phrases: Mapped[list] = mapped_column(JSONB, nullable=True)


class SlangPhrase(Base):
	"""Thư viện cụm thoại/slang có nguồn tham chiếu (feature-speaking.md mục 4)."""

	__tablename__ = "slang_phrases"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	phrase_text: Mapped[str] = mapped_column(String(150))
	meaning: Mapped[str] = mapped_column(Text)
	example_sentence: Mapped[str] = mapped_column(Text, nullable=True)
	formality_level: Mapped[str] = mapped_column(String(20), server_default=text("'neutral'"))
	topic_tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
	source_reference: Mapped[str] = mapped_column(String(150))


class PhrasebookEntry(Base):
	"""Cụm đã lưu vào sổ tay: tham chiếu thư viện HOẶC snapshot (mục 2.2, 2.4)."""

	__tablename__ = "user_phrasebook_entries"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	slang_phrase_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("slang_phrases.id", ondelete="SET NULL"), nullable=True
	)
	conversation_turn_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("conversation_turns.id", ondelete="SET NULL"), nullable=True
	)
	phrase_text: Mapped[str] = mapped_column(String(150))
	meaning: Mapped[str] = mapped_column(Text, nullable=True)
	example_sentence: Mapped[str] = mapped_column(Text, nullable=True)
	formality_level: Mapped[str] = mapped_column(String(20), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, server_default=text("now()"))
