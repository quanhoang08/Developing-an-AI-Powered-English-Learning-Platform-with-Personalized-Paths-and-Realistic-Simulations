"""Nhật ký hoạt động (XP theo tuần, tự chấm bài giao) và báo cáo mẹo nhớ (backlog 4.6, 5.1, 3.7).

Idempotent như các migration trước; chỉ thêm bảng mới, không đổi dữ liệu cũ.
"""

from alembic import op


revision = "20261004_0032"
down_revision = "20261003_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_log (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            activity varchar(40) NOT NULL,
            xp integer NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_activity_log_user_created ON activity_log (user_id, created_at DESC)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mnemonic_reports (
            mnemonic_id uuid NOT NULL REFERENCES mnemonics(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (mnemonic_id, user_id)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mnemonic_reports")
    op.execute("DROP TABLE IF EXISTS activity_log")
