"""Add the external source URL required by Vocabulary and Extension flows."""

from alembic import op
from sqlalchemy import Column, Text, inspect, text


revision = "20260906_0003"
down_revision = "20260905_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add source_url only when an older schema does not already contain it."""
    # Inspect the live table so this migration works with both old and fresh DBs.
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("vocab_items")}
    if "source_url" not in columns:
        op.add_column("vocab_items", Column("source_url", Text(), nullable=True))

    # Enforce the documented rule: exactly one of document_id/source_url is set.
    op.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'chk_vocab_source_exactly_one'
                ) THEN
                    ALTER TABLE vocab_items
                    ADD CONSTRAINT chk_vocab_source_exactly_one
                    CHECK ((document_id IS NOT NULL) <> (source_url IS NOT NULL));
                END IF;
            END $$;
            """
        )
    )


def downgrade() -> None:
    """Keep user vocabulary data intact during baseline downgrade."""
    # Do not remove source_url because it may contain user-created vocabulary links.
    pass
