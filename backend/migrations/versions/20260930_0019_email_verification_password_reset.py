"""users.email_verified_at + bảng auth_tokens (mã OTP 6 số xác minh email / đặt lại mật khẩu).

User đang tồn tại được coi là đã xác minh. Idempotent như các migration trước.
"""

from alembic import op


revision = "20260930_0019"
down_revision = "20260927_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at timestamptz")
    op.execute("UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_tokens (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            purpose varchar(20) NOT NULL CHECK (purpose IN ('verify_email', 'reset_password')),
            token_hash varchar(255) NOT NULL,
            expires_at timestamptz NOT NULL,
            used_at timestamptz,
            attempts integer NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_auth_tokens_user_purpose ON auth_tokens (user_id, purpose)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS auth_tokens")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS email_verified_at")
