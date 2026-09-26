"""Add rephrase_requests.explanation, required by the AI Rephrase feature (feature-writing.md mục 3)."""

from alembic import op
from sqlalchemy import Column, Text, inspect


revision = "20260917_0007"
down_revision = "20260917_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add explanation only when an older schema.sql bootstrap lacks it."""
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("rephrase_requests")}
    if "explanation" not in columns:
        # schema.sql gốc chỉ có original_text/rephrased_text/style_target — thiếu chỗ lưu lý do
        # gợi ý (bắt buộc theo business rule "kèm giải thích ngắn vì sao phương án đó tốt hơn").
        op.add_column("rephrase_requests", Column("explanation", Text(), nullable=True))


def downgrade() -> None:
    """Keep rephrase history intact; non-destructive baseline."""
    pass
