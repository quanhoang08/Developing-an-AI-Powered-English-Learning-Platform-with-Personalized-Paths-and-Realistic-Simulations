"""Thêm document_chunks.embedding_local vector(1024) cho embedding bge-m3 chạy local qua Ollama.

Chỉ THÊM cột (nullable) — cột embedding 768 chiều của Gemini giữ nguyên nên không mất dữ liệu và có
thể quay lại provider cũ. Chunk cũ chưa có embedding_local cho tới khi chạy
`python scripts/reindex_embeddings.py`.
"""

from alembic import op
from sqlalchemy import inspect, text


revision = "20260919_0011"
down_revision = "20260919_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("document_chunks")}
    if "embedding_local" not in columns:
        op.execute(text("ALTER TABLE document_chunks ADD COLUMN embedding_local vector(1024)"))


def downgrade() -> None:
    op.execute(text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding_local"))
