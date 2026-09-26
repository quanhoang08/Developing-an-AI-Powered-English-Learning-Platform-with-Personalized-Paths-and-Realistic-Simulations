"""Extend personas/podcasts/dictation_attempts for the Dictation feature and create
user_errors (Adaptive Learning Engine), required by feature-listening.md mục 1, 3.

Bối cảnh: root schema.sql (bản Docker thật sự dùng để khởi tạo volume postgres_data lần
đầu) đã có sẵn personas/podcasts/transcript_segments/dictation_attempts nhưng thiếu vài cột
mà feature-listening.md yêu cầu (is_active, persona_id số ít, status, start/end_word_index,
reference_word_tags) — đúng tinh thần "bảo thủ về schema": mở rộng bảng có sẵn thay vì tạo
bảng mới. user_errors hoàn toàn chưa tồn tại (DB thật vẫn còn bảng error_log cũ, generic).
"""

from alembic import op
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, inspect, text
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "20260917_0008"
down_revision = "20260917_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    persona_columns = {column["name"] for column in inspector.get_columns("personas")}
    if "is_active" not in persona_columns:
        op.add_column(
            "personas", Column("is_active", Boolean(), nullable=False, server_default=text("true"))
        )
    if "created_at" not in persona_columns:
        op.add_column(
            "personas",
            Column("created_at", DateTime(timezone=True), nullable=True, server_default=text("now()")),
        )

    podcast_columns = {column["name"] for column in inspector.get_columns("podcasts")}
    if "persona_id" not in podcast_columns:
        # Thay cho persona_ids[] cũ (đa giọng đọc) — spec chỉ dùng 1 persona_id/podcast
        # (feature-listening.md mục 1.2). Bảng podcasts rỗng (chưa có code nào tạo dòng nào),
        # an toàn drop cột cũ không dùng.
        op.add_column(
            "podcasts",
            Column(
                "persona_id",
                UUID(as_uuid=True),
                ForeignKey("personas.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    if "persona_ids" in podcast_columns:
        op.drop_column("podcasts", "persona_ids")
    if "status" not in podcast_columns:
        op.add_column(
            "podcasts",
            Column("status", String(20), nullable=False, server_default=text("'processing'")),
        )

    dictation_columns = {column["name"] for column in inspector.get_columns("dictation_attempts")}
    if "start_word_index" not in dictation_columns:
        op.add_column("dictation_attempts", Column("start_word_index", Integer(), nullable=True))
    if "end_word_index" not in dictation_columns:
        op.add_column("dictation_attempts", Column("end_word_index", Integer(), nullable=True))
    if "audio_segment_path" not in dictation_columns:
        op.add_column("dictation_attempts", Column("audio_segment_path", Text(), nullable=True))
    if "reference_word_tags" not in dictation_columns:
        op.add_column(
            "dictation_attempts",
            Column(
                "reference_word_tags",
                JSONB(),
                nullable=False,
                server_default=text("'[]'::jsonb"),
            ),
        )

    if not inspector.has_table("user_errors"):
        op.create_table(
            "user_errors",
            Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")),
            Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            # Dictation không tạo quiz_attempts nên luôn để NULL khi ghi từ listening_service;
            # cột này chỉ có ý nghĩa khi Adaptive Learning Engine/Rearrange the Block build sau.
            Column(
                "quiz_attempt_id",
                UUID(as_uuid=True),
                ForeignKey("quiz_attempts.id", ondelete="SET NULL"),
                nullable=True,
            ),
            Column("error_type", String(30), nullable=False),
            Column("spaced_repetition_level", Integer(), nullable=False, server_default=text("0")),
            Column("created_at", DateTime(timezone=True), nullable=True, server_default=text("now()")),
        )
        op.execute(
            text(
                """
                ALTER TABLE user_errors
                ADD CONSTRAINT chk_user_errors_error_type_valid
                CHECK (error_type IN (
                    'grammar', 'vocabulary', 'spelling', 'pronunciation',
                    'listening_comprehension', 'reading_comprehension',
                    'writing_coherence', 'communicative_intent', 'politeness'
                ));
                """
            )
        )
        op.create_index("idx_user_errors_user_id_error_type", "user_errors", ["user_id", "error_type"])


def downgrade() -> None:
    """Non-destructive baseline, consistent with the rest of this migration history."""
    pass
