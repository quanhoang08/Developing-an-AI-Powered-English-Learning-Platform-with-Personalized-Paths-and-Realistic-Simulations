"""Bảng grammar_attempts: lịch sử bản đồ ngữ pháp theo chủ điểm để so sánh giữa các lần (backlog 3.8).

Idempotent như các migration trước.
"""

from alembic import op


revision = "20261003_0029"
down_revision = "20261003_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS grammar_attempts (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            topic varchar(30),
            score integer NOT NULL,
            total integer NOT NULL,
            by_topic jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_grammar_attempts_user_created ON grammar_attempts (user_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS grammar_attempts")
