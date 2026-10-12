"""Bảng live_calls: lịch sử cuộc gọi thoại 2 chiều qua Gemini Live (F22) — transcript dạng chữ.

Idempotent như các migration trước.
"""

from alembic import op


revision = "20261012_0035"
down_revision = "20261008_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS live_calls (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            scenario_id uuid REFERENCES scenarios(id) ON DELETE SET NULL,
            duration_seconds integer NOT NULL,
            transcript jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_live_calls_user_created ON live_calls (user_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS live_calls")
