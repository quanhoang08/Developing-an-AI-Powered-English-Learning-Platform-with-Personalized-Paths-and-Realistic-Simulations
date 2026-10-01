"""Đổi tên "vietnglish" thành "literal_translation" (cột conversation_turns + nguồn trong user_errors).

Idempotent như các migration trước.
"""

from alembic import op


revision = "20261001_0021"
down_revision = "20261001_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'conversation_turns' AND column_name = 'vietnglish'
            ) THEN
                ALTER TABLE conversation_turns RENAME COLUMN vietnglish TO literal_translation;
            END IF;
        END $$
        """
    )
    op.execute(
        "UPDATE user_errors SET detail = jsonb_set(detail, '{source}', '\"speaking_literal_translation\"') "
        "WHERE detail->>'source' = 'speaking_vietnglish'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE user_errors SET detail = jsonb_set(detail, '{source}', '\"speaking_vietnglish\"') "
        "WHERE detail->>'source' = 'speaking_literal_translation'"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'conversation_turns' AND column_name = 'literal_translation'
            ) THEN
                ALTER TABLE conversation_turns RENAME COLUMN literal_translation TO vietnglish;
            END IF;
        END $$
        """
    )
