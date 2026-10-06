"""Bảng toeic_bank: ngân hàng đề TOEIC-style đã kiểm chứng sẵn, phát ngay khi người học bấm Start (backlog 2.7).

Idempotent như các migration trước.
"""

from alembic import op


revision = "20261003_0028"
down_revision = "20261002_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS toeic_bank (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            part smallint NOT NULL,
            unit jsonb NOT NULL,
            source varchar(20) NOT NULL,
            disabled boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_toeic_bank_part ON toeic_bank (part) WHERE NOT disabled")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS toeic_bank")
