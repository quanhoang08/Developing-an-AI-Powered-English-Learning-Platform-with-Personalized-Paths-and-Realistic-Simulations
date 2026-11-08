"""Đổi classes.teacher_id -> owner_id: nhóm học do bất kỳ người dùng nào tạo, không có vai giáo viên.

Chỉ đổi tên cột/index, giữ nguyên dữ liệu. Idempotent như các migration trước.
"""

from alembic import op
from sqlalchemy import inspect


revision = "20261108_0037"
down_revision = "20261023_0036"
branch_labels = None
depends_on = None


def _has_column(name: str) -> bool:
    return name in {c["name"] for c in inspect(op.get_bind()).get_columns("classes")}


def upgrade() -> None:
    if _has_column("teacher_id") and not _has_column("owner_id"):
        op.execute("ALTER TABLE classes RENAME COLUMN teacher_id TO owner_id")
    op.execute("ALTER INDEX IF EXISTS ix_classes_teacher RENAME TO ix_classes_owner")


def downgrade() -> None:
    if _has_column("owner_id") and not _has_column("teacher_id"):
        op.execute("ALTER TABLE classes RENAME COLUMN owner_id TO teacher_id")
    op.execute("ALTER INDEX IF EXISTS ix_classes_owner RENAME TO ix_classes_teacher")
