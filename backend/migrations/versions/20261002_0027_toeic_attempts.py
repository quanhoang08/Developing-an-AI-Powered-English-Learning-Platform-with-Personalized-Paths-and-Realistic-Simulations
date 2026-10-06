"""Bảng toeic_attempts: lượt luyện TOEIC-style (Part 2/5/6/7) để chấm ở server và thống kê theo Part (backlog 2.7).

Idempotent như các migration trước.
"""

from alembic import op


revision = "20261002_0027"
down_revision = "20261002_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS toeic_attempts (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            part smallint NOT NULL,
            questions jsonb NOT NULL,
            picks jsonb,
            correct_count integer,
            score numeric(5,2),
            submitted_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_toeic_attempts_user_created ON toeic_attempts (user_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS toeic_attempts")
