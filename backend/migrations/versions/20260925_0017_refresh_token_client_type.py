"""refresh_tokens.client_type ('web' | 'extension') cho middleware giới hạn token extension.

Dòng cũ mặc định 'web'. Idempotent như các migration trước.
"""

from alembic import op


revision = "20260925_0017"
down_revision = "20260924_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS client_type varchar(20) NOT NULL DEFAULT 'web'")
    op.execute("ALTER TABLE refresh_tokens DROP CONSTRAINT IF EXISTS chk_refresh_tokens_client_type")
    op.execute(
        "ALTER TABLE refresh_tokens ADD CONSTRAINT chk_refresh_tokens_client_type "
        "CHECK (client_type IN ('web', 'extension'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE refresh_tokens DROP CONSTRAINT IF EXISTS chk_refresh_tokens_client_type")
    op.execute("ALTER TABLE refresh_tokens DROP COLUMN IF EXISTS client_type")
