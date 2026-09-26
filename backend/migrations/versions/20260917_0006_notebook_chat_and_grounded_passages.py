"""Add Notebook chat (RAG Q&A) and document-grounded Skim & Scan passages."""

from alembic import op
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, inspect, text
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "20260917_0006"
down_revision = "20260916_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add source_document_id + notebook_chat_messages only when missing."""
    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Skim & Scan có thể sinh đoạn văn từ 1 tài liệu đã upload thay vì luôn tự do theo topic
    # — cột này (nullable) ghi lại nguồn gốc khi generated_passages.content được trích từ
    # document_chunks của user, phục vụ hiển thị lại/traceability.
    passage_columns = {
        column["name"] for column in inspect(bind).get_columns("generated_passages")
    }
    if "source_document_id" not in passage_columns:
        op.add_column(
            "generated_passages",
            Column(
                "source_document_id",
                UUID(as_uuid=True),
                ForeignKey("documents.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(
            "idx_generated_passages_source_document",
            "generated_passages",
            ["source_document_id"],
        )

    # Lịch sử hội thoại kiểu NotebookLM — mỗi document có 1 luồng chat riêng của user sở hữu.
    if "notebook_chat_messages" not in existing_tables:
        op.create_table(
            "notebook_chat_messages",
            Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=text("uuid_generate_v4()"),
            ),
            Column(
                "document_id",
                UUID(as_uuid=True),
                ForeignKey("documents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            Column(
                "user_id",
                UUID(as_uuid=True),
                ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            Column("role", String(10), nullable=False),
            Column("content", Text(), nullable=False),
            # JSONB mảng {chunk_id, excerpt} — chỉ set cho role='assistant', phục vụ hiển thị
            # trích dẫn nguồn dưới mỗi câu trả lời (giống NotebookLM show citation).
            Column("sources", JSONB(), nullable=True),
            Column("created_at", DateTime(timezone=True), server_default=text("now()")),
        )
        op.create_index(
            "idx_notebook_chat_messages_document",
            "notebook_chat_messages",
            ["document_id", "created_at"],
        )
        op.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'chk_notebook_chat_role_valid'
                    ) THEN
                        ALTER TABLE notebook_chat_messages
                        ADD CONSTRAINT chk_notebook_chat_role_valid
                        CHECK (role IN ('user', 'assistant'));
                    END IF;
                END $$;
                """
            )
        )


def downgrade() -> None:
    """Keep chat history and passage provenance intact; non-destructive baseline."""
    pass
