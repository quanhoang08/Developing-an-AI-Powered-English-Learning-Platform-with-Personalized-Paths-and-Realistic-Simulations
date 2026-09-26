"""Extend writing_submissions for the 3-source Writing module (document_summary/extended_topic/free_topic)."""

from alembic import op
from sqlalchemy import Column, DateTime, String, Text, inspect, text
from sqlalchemy.dialects.postgresql import JSONB


revision = "20260916_0005"
down_revision = "20260906_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add columns/constraints only when an older schema.sql bootstrap lacks them."""
    # Inspect first so this works on both the Docker-initialized DB and a fresh one.
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("writing_submissions")}

    if "source_type" not in columns:
        op.add_column(
            "writing_submissions",
            Column("source_type", String(20), nullable=False, server_default=text("'document_summary'")),
        )
    if "prompt_text" not in columns:
        op.add_column("writing_submissions", Column("prompt_text", Text(), nullable=True))
    if "certificate_style" not in columns:
        op.add_column("writing_submissions", Column("certificate_style", String(20), nullable=True))
    if "rubric_scores" not in columns:
        op.add_column("writing_submissions", Column("rubric_scores", JSONB(), nullable=True))
    if "completed_at" not in columns:
        op.add_column("writing_submissions", Column("completed_at", DateTime(timezone=True), nullable=True))

    # prompt_type is superseded by source_type; the table has no application writers yet
    # (Writing module was never implemented before this revision), so dropping is safe.
    if "prompt_type" in columns:
        op.drop_column("writing_submissions", "prompt_type")

    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_writing_source_type_valid'
                ) THEN
                    ALTER TABLE writing_submissions
                    ADD CONSTRAINT chk_writing_source_type_valid
                    CHECK (source_type IN ('document_summary', 'extended_topic', 'free_topic'));
                END IF;
            END $$;
            """
        )
    )
    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_writing_document_id_by_source'
                ) THEN
                    ALTER TABLE writing_submissions
                    ADD CONSTRAINT chk_writing_document_id_by_source
                    CHECK (
                        (source_type IN ('document_summary', 'extended_topic') AND document_id IS NOT NULL)
                        OR (source_type = 'free_topic' AND document_id IS NULL)
                    );
                END IF;
            END $$;
            """
        )
    )
    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_writing_certificate_style_valid'
                ) THEN
                    ALTER TABLE writing_submissions
                    ADD CONSTRAINT chk_writing_certificate_style_valid
                    CHECK (certificate_style IS NULL OR certificate_style IN ('toeic', 'ielts', 'cambridge'));
                END IF;
            END $$;
            """
        )
    )


def downgrade() -> None:
    """Keep submissions intact during downgrade; this baseline is non-destructive."""
    pass
