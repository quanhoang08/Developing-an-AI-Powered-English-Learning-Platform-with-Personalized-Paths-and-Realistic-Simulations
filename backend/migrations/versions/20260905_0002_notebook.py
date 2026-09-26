"""Ensure the Notebook folder and document tables exist.

Docker creates these tables from schema.sql, so the migration checks the
current database before creating anything. This keeps local and container
setups idempotent.
"""

from alembic import op
from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, String, Text, inspect, text
from sqlalchemy.dialects.postgresql import UUID


revision = "20260905_0002"
down_revision = "20260905_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create missing Notebook tables without replacing existing data."""
    # Inspect first because schema.sql may already have created the full schema.
    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Folders must exist before documents can reference them.
    if "notebook_folders" not in existing_tables:
        op.create_table(
            "notebook_folders",
            op.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=text("uuid_generate_v4()"),
            ),
            op.Column(
                "user_id",
                UUID(as_uuid=True),
                ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            op.Column("name", String(100), nullable=False),
            op.Column("created_at", DateTime(timezone=True), server_default=text("now()")),
        )
        op.create_index("idx_notebook_folders_user", "notebook_folders", ["user_id"])

    # Documents store metadata and the path to the uploaded source file.
    if "documents" not in existing_tables:
        op.create_table(
            "documents",
            op.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=text("uuid_generate_v4()"),
            ),
            op.Column(
                "user_id",
                UUID(as_uuid=True),
                ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            op.Column(
                "folder_id",
                UUID(as_uuid=True),
                ForeignKey("notebook_folders.id", ondelete="SET NULL"),
                nullable=True,
            ),
            op.Column("title", String(255), nullable=False),
            op.Column("source_type", String(20), nullable=False),
            op.Column("source_url", Text, nullable=True),
            op.Column("file_path", Text, nullable=True),
            op.Column("file_size_kb", Integer, nullable=True),
            op.Column("tags", ARRAY(String), nullable=True),
            op.Column("starred", Boolean, server_default=text("false")),
            op.Column("language", String(10), server_default=text("'en'")),
            op.Column("status", String(20), server_default=text("'processing'")),
            op.Column("created_at", DateTime(timezone=True), server_default=text("now()")),
        )
        op.create_index("idx_documents_user", "documents", ["user_id"])
        op.create_index("idx_documents_folder", "documents", ["folder_id"])


def downgrade() -> None:
    """Keep baseline Notebook data intact during downgrade."""
    # These tables are also owned by schema.sql; dropping them could delete
    # user content, so this baseline migration is intentionally non-destructive.
    pass
