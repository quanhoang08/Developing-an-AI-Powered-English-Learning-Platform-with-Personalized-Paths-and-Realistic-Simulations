"""Add completion timestamp required for idempotent Reading submissions."""

from alembic import op
from sqlalchemy import Column, DateTime, inspect


revision = "20260906_0004"
down_revision = "20260906_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add completed_at when the existing schema does not have it."""
    # Inspect first so Docker's schema.sql and older local databases both work.
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("reading_sessions")}
    if "completed_at" not in columns:
        op.add_column("reading_sessions", Column("completed_at", DateTime(timezone=True)))


def downgrade() -> None:
    """Keep completion history during downgrade because it is user progress data."""
    pass
