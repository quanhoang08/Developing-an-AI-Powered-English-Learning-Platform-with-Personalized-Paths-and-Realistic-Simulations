"""Bảng ielts_attempts: lưu mỗi bài IELTS Speaking giả lập (band, nhận xét, transcript) để xem tiến bộ.

Idempotent như các migration trước.
"""

from alembic import op


revision = "20261001_0023"
down_revision = "20261001_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ielts_attempts (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            topic varchar(80),
            overall numeric(2,1) NOT NULL,
            fluency_coherence numeric(2,1) NOT NULL,
            lexical_resource numeric(2,1) NOT NULL,
            grammatical_range numeric(2,1) NOT NULL,
            pronunciation numeric(2,1),
            words_per_minute integer,
            feedback_vi text NOT NULL,
            answers jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ielts_attempts_user_created ON ielts_attempts (user_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ielts_attempts")
