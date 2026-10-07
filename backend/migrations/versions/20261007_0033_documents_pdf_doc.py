"""Notebook nhận thêm .pdf và .doc (bỏ upload audio mới).

Giữ 'audio' trong CHECK để các record audio cũ vẫn hợp lệ; chỉ nới constraint, không đổi dữ liệu.
"""

from alembic import op


revision = "20261007_0033"
down_revision = "20261004_0032"
branch_labels = None
depends_on = None


def _replace_source_type_check(values: str) -> None:
    op.execute("ALTER TABLE documents DROP CONSTRAINT IF EXISTS chk_documents_source_type_valid")
    op.execute(f"ALTER TABLE documents ADD CONSTRAINT chk_documents_source_type_valid CHECK (source_type IN ({values}))")


def upgrade() -> None:
    _replace_source_type_check("'audio', 'docx', 'doc', 'pdf'")


def downgrade() -> None:
    # Thất bại nếu đã có document pdf/doc — xoá chúng trước khi downgrade.
    _replace_source_type_check("'audio', 'docx'")
