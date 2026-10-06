"""Gỡ hồ sơ phụ huynh (backlog 5.2, 5.3 đã bỏ): xoá users.birth_year/parent_email/parent_consent_at,
xoá token OTP 'parent_consent' và trả CHECK auth_tokens.purpose về 2 giá trị ban đầu.

Idempotent như các migration trước. Downgrade thêm lại cột (dữ liệu đã xoá không khôi phục được).
"""

from alembic import op
from sqlalchemy import Column, SmallInteger, String, inspect
from sqlalchemy.dialects.postgresql import TIMESTAMP


revision = "20261003_0031"
down_revision = "20261003_0030"
branch_labels = None
depends_on = None


def _set_purpose_check(values: str) -> None:
    op.execute(
        f"""
        DO $$
        DECLARE c text;
        BEGIN
            FOR c IN SELECT conname FROM pg_constraint
                     WHERE conrelid = 'auth_tokens'::regclass AND contype = 'c'
                       AND pg_get_constraintdef(oid) LIKE '%purpose%'
            LOOP
                EXECUTE format('ALTER TABLE auth_tokens DROP CONSTRAINT %I', c);
            END LOOP;
            ALTER TABLE auth_tokens ADD CONSTRAINT auth_tokens_purpose_check CHECK (purpose IN ({values}));
        END $$
        """
    )


def upgrade() -> None:
    # Phải xoá token cũ trước, nếu không CHECK mới sẽ từ chối các dòng 'parent_consent' còn sót.
    op.execute("DELETE FROM auth_tokens WHERE purpose = 'parent_consent'")
    _set_purpose_check("'verify_email', 'reset_password'")
    for column in ("birth_year", "parent_email", "parent_consent_at"):
        op.execute(f"ALTER TABLE users DROP COLUMN IF EXISTS {column}")


def downgrade() -> None:
    existing = {c["name"] for c in inspect(op.get_bind()).get_columns("users")}
    for column in (
        Column("birth_year", SmallInteger, nullable=True),
        Column("parent_email", String(255), nullable=True),
        Column("parent_consent_at", TIMESTAMP(timezone=True), nullable=True),
    ):
        if column.name not in existing:
            op.add_column("users", column)
    _set_purpose_check("'verify_email', 'reset_password', 'parent_consent'")
