"""users.target_band + users.exam_date: mục tiêu band IELTS và ngày thi cho kế hoạch học (backlog 2.5).

Hai cột đều nullable nên user cũ không bị ảnh hưởng. Idempotent như các migration trước.
"""

from alembic import op
from sqlalchemy import Column, Date, Numeric, inspect


revision = "20261002_0025"
down_revision = "20261002_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {c["name"] for c in inspect(op.get_bind()).get_columns("users")}
    if "target_band" not in existing:
        op.add_column("users", Column("target_band", Numeric(2, 1), nullable=True))
    if "exam_date" not in existing:
        op.add_column("users", Column("exam_date", Date(), nullable=True))


def downgrade() -> None:
    """Giữ nguyên dữ liệu đã ghi; không xoá cột (đúng quy ước các migration trước)."""
