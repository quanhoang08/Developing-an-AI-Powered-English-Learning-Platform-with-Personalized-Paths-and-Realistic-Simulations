"""Lưu tóm tắt AI + câu hỏi gợi ý của document (tab Content của Notebook).

JSONB {"summary": str, "questions": [str]}, NULL = chưa sinh. Idempotent như các migration khác.
"""

from alembic import op


revision = "20261008_0034"
down_revision = "20261007_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS overview JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS overview")
