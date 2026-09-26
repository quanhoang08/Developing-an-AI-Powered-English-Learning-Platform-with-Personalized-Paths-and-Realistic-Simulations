"""Thêm streaks.total_xp để lưu XP cùng chỗ với streak (Gamification, api-spec mục 7).

Bảng streaks đã có sẵn trong schema.sql (user_id, current_streak, longest_streak,
last_active_date); ERD gốc chưa có cột XP nên chỉ THÊM cột total_xp, không đụng dữ liệu cũ.
Chưa có backfill: XP và streak chỉ tính từ các hoạt động hoàn thành sau khi migration này chạy.
"""

from alembic import op
from sqlalchemy import Column, Date, ForeignKey, Integer, inspect, text
from sqlalchemy.dialects.postgresql import UUID


revision = "20260920_0012"
down_revision = "20260919_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # DB dựng từ schema.sql đã có bảng; nhánh create_table chỉ để DB trống vẫn chạy được.
    if "streaks" not in inspector.get_table_names():
        op.create_table(
            "streaks",
            Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
            Column("current_streak", Integer(), server_default=text("0")),
            Column("longest_streak", Integer(), server_default=text("0")),
            Column("last_active_date", Date(), nullable=True),
            Column("total_xp", Integer(), server_default=text("0")),
        )
        return

    columns = {column["name"] for column in inspector.get_columns("streaks")}
    if "total_xp" not in columns:
        op.add_column("streaks", Column("total_xp", Integer(), server_default=text("0")))


def downgrade() -> None:
    """Giữ nguyên dữ liệu streak/XP đã ghi; không xoá cột."""
    pass
