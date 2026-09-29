"""Study time tracking (Dashboard "This week, in minutes" + "Pick up where you left off"):

- users.timer_mode_enabled (boolean, default false): người dùng tự bật "chế độ bấm giờ" — KHÔNG
  đo thời gian mặc định cho ai, chỉ log khi user chủ động bật (quyết định người dùng 2026-09-27).
- study_time_log (mới): 1 dòng / 1 hoạt động đã hoàn thành trong lúc timer mode đang bật, ghi cùng
  transaction với gamification_service.award_activity. Dùng để tính "phút học trong tuần" theo kỹ
  năng ở GET /api/activity/weekly-summary — dữ liệu thật, không suy diễn từ hoạt động khác.
"""

from alembic import op
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, inspect, text
from sqlalchemy.dialects.postgresql import UUID


revision = "20260927_0018"
down_revision = "20260925_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())

    if "timer_mode_enabled" not in {c["name"] for c in inspector.get_columns("users")}:
        op.add_column(
            "users",
            Column("timer_mode_enabled", Boolean(), nullable=False, server_default=text("false")),
        )

    if "study_time_log" not in set(inspector.get_table_names()):
        op.create_table(
            "study_time_log",
            Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")),
            Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            Column("skill", String(20), nullable=False),
            Column("duration_seconds", Integer(), nullable=False),
            Column("created_at", DateTime(timezone=True), server_default=text("now()")),
            CheckConstraint(
                "skill IN ('reading', 'listening', 'writing', 'speaking')",
                name="chk_study_time_log_skill_valid",
            ),
            CheckConstraint("duration_seconds > 0", name="chk_study_time_log_duration_positive"),
        )
        op.create_index(
            "idx_study_time_log_user_created", "study_time_log", ["user_id", "created_at"]
        )


def downgrade() -> None:
    """Giữ nguyên dữ liệu đã ghi; không xoá cột/bảng (đúng quy ước các migration trước)."""
    pass
