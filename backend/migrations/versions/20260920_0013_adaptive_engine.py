"""Adaptive Learning Engine: thêm cột còn thiếu để sinh đề động và chấm lượt làm bài.

- user_errors.detail (JSONB): nội dung lỗi cụ thể (câu gốc, bản sửa, giải thích) — bảng cũ chỉ có
  error_type nên không đủ dữ liệu để sinh câu hỏi luyện đúng lỗi user từng mắc.
- quizzes.focus_error_types (JSONB): tham số focus_error_types của POST /api/adaptive/quizzes/generate.
- quiz_attempts.quiz_id (FK -> quizzes.id): lượt làm bài thuộc bộ đề nào (thiet_ke_database.md mục 9.2).
Các bảng quizzes/quiz_attempts/review_priority_queue đã có sẵn trong schema.sql nên chỉ THÊM cột.
"""

from alembic import op
from sqlalchemy import Column, ForeignKey, inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "20260920_0013"
down_revision = "20260920_0012"
branch_labels = None
depends_on = None


def _columns(inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    inspector = inspect(op.get_bind())

    if "detail" not in _columns(inspector, "user_errors"):
        op.add_column("user_errors", Column("detail", JSONB(), nullable=True))
    if "focus_error_types" not in _columns(inspector, "quizzes"):
        op.add_column("quizzes", Column("focus_error_types", JSONB(), nullable=True))
    if "quiz_id" not in _columns(inspector, "quiz_attempts"):
        op.add_column(
            "quiz_attempts",
            Column("quiz_id", UUID(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=True),
        )


def downgrade() -> None:
    """Giữ nguyên dữ liệu đã ghi; không xoá cột."""
    pass
