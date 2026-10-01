"""Thêm reading_answers.explanation (giải thích đáp án True/False/Not Given).

Idempotent như các migration trước.
"""

from alembic import op


revision = "20261001_0022"
down_revision = "20261001_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE reading_answers ADD COLUMN IF NOT EXISTS explanation TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE reading_answers DROP COLUMN IF EXISTS explanation")
