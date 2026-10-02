"""Bảng listening_quiz_attempts: lưu quiz nghe hiểu (câu hỏi, đáp án đã chọn, điểm) để xem lại và ghi lỗi.

Idempotent như các migration trước.
"""

from alembic import op


revision = "20261002_0024"
down_revision = "20261001_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS listening_quiz_attempts (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            podcast_id uuid NOT NULL REFERENCES podcasts(id) ON DELETE CASCADE,
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
        "CREATE INDEX IF NOT EXISTS ix_listening_quiz_user_created ON listening_quiz_attempts (user_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS listening_quiz_attempts")
