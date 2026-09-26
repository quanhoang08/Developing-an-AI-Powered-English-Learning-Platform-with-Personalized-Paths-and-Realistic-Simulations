"""Baseline authentication tables for the existing Lumina schema.

This revision is intentionally idempotent because Docker initializes the full
schema from schema.sql before Alembic runs. Alembic therefore records this
revision without recreating tables that already exist.
"""

from alembic import op
from sqlalchemy import Boolean, DateTime, ForeignKey, String, inspect, text
from sqlalchemy.dialects.postgresql import UUID


revision = "20260905_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Ensure the authentication tables exist before application startup."""
    # Read the current database first so this migration is safe on both:
    # a Docker database initialized by schema.sql and an empty database.
    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())

    # The UUID extension supplies the default id generator used by the schema.
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Create users only when the table was not already created by schema.sql.
    if "users" not in existing_tables:
        op.create_table(
            "users",
            op.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=text("uuid_generate_v4()"),
            ),
            op.Column("email", String(255), nullable=False, unique=True),
            op.Column("password_hash", String(255), nullable=False),
            op.Column("display_name", String(100), nullable=True),
            op.Column("native_language", String(10), server_default=text("'vi'")),
            op.Column("target_level", String(10), nullable=True),
            op.Column("created_at", DateTime(timezone=True), server_default=text("now()")),
            op.Column("updated_at", DateTime(timezone=True), server_default=text("now()")),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=False)

    # Create refresh_tokens only when the table does not already exist.
    if "refresh_tokens" not in existing_tables:
        op.create_table(
            "refresh_tokens",
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
            op.Column("token_hash", String(255), nullable=False, unique=True),
            op.Column("is_revoked", Boolean, server_default=text("false")),
            op.Column("expires_at", DateTime(timezone=True), nullable=False),
            op.Column("created_at", DateTime(timezone=True), server_default=text("now()")),
        )
        op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])


def downgrade() -> None:
    """Keep baseline tables intact; schema.sql owns the full database lifecycle."""
    # This is a baseline marker for a database already initialized by schema.sql.
    # Dropping tables here could destroy unrelated feature data, so downgrade is
    # intentionally non-destructive. Future feature migrations remain reversible.
    pass
