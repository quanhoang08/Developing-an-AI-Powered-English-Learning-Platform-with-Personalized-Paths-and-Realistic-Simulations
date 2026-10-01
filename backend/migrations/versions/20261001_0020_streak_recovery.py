"""streaks.lost_streak + lost_on: ghi nhớ chuỗi vừa đứt để user khôi phục bằng quiz 10-15 câu;
streaks.freezes_available: freeze tặng mỗi 7 ngày học liên tiếp, tự dùng khi bỏ lỡ ngày.

Idempotent như các migration trước.
"""

from alembic import op


revision = "20261001_0020"
down_revision = "20260930_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE streaks ADD COLUMN IF NOT EXISTS lost_streak integer NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE streaks ADD COLUMN IF NOT EXISTS lost_on date")
    op.execute("ALTER TABLE streaks ADD COLUMN IF NOT EXISTS freezes_available integer NOT NULL DEFAULT 0")
    # Speaking: "nói lại cho tự nhiên" + cảnh báo Vietnglish lưu theo từng lượt để xem lại ở phiên cũ.
    op.execute("ALTER TABLE conversation_turns ADD COLUMN IF NOT EXISTS natural_rephrase text")
    op.execute("ALTER TABLE conversation_turns ADD COLUMN IF NOT EXISTS vietnglish jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE conversation_turns DROP COLUMN IF EXISTS vietnglish")
    op.execute("ALTER TABLE conversation_turns DROP COLUMN IF EXISTS natural_rephrase")
    op.execute("ALTER TABLE streaks DROP COLUMN IF EXISTS freezes_available")
    op.execute("ALTER TABLE streaks DROP COLUMN IF EXISTS lost_on")
    op.execute("ALTER TABLE streaks DROP COLUMN IF EXISTS lost_streak")
