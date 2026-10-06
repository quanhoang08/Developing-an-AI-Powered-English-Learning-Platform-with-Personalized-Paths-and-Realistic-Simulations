"""Bảng mnemonics + mnemonic_votes: mẹo nhớ tiếng Việt do người học tạo và bình chọn (backlog 3.7).

Idempotent như các migration trước.
"""

from alembic import op


revision = "20261002_0026"
down_revision = "20261002_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mnemonics (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            term_key varchar(100) NOT NULL,
            text varchar(300) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_mnemonics_user_term ON mnemonics (user_id, term_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mnemonics_term ON mnemonics (term_key)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mnemonic_votes (
            mnemonic_id uuid NOT NULL REFERENCES mnemonics(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            PRIMARY KEY (mnemonic_id, user_id)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mnemonic_votes")
    op.execute("DROP TABLE IF EXISTS mnemonics")
