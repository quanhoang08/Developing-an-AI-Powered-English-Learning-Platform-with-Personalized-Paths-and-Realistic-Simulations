"""Rearrange the Block: quiz_attempts phải chứa được lượt làm không thuộc bộ đề nào.

- quiz_attempts.quiz_id -> NULLABLE (thiet_ke_database.md mục 9.2: luôn NULL với Rearrange). Schema
  gốc khai báo NOT NULL, migration 0013 chỉ thêm cột khi chưa có nên không sửa ràng buộc này.
- attempt_type: 'rearrange_reading' | 'rearrange_writing' (NULL với lượt làm đề Adaptive).
- is_open_form: cờ dạng mở/đóng, chốt lúc sinh đề, không đổi khi chấm (feature-writing.md mục 4.3).
- payload (JSONB): khối theo thứ tự chuẩn, các thứ tự được chấp nhận và lỗi nguồn của bài.
Chỉ THÊM cột / nới ràng buộc, không đổi dữ liệu cũ.
"""

from alembic import op
from sqlalchemy import Boolean, Column, String, inspect
from sqlalchemy.dialects.postgresql import JSONB


revision = "20260924_0014"
down_revision = "20260920_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("quiz_attempts")}

    op.alter_column("quiz_attempts", "quiz_id", nullable=True)
    if "attempt_type" not in existing:
        op.add_column("quiz_attempts", Column("attempt_type", String(30), nullable=True))
    if "is_open_form" not in existing:
        op.add_column("quiz_attempts", Column("is_open_form", Boolean(), nullable=True))
    if "payload" not in existing:
        op.add_column("quiz_attempts", Column("payload", JSONB(), nullable=True))


def downgrade() -> None:
    """Giữ nguyên dữ liệu đã ghi; không xoá cột."""
    pass
