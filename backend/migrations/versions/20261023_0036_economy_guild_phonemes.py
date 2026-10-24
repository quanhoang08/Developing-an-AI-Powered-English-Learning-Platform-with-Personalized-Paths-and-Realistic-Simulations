"""Ví xu/tim/booster, kho đồ, bang hội, thống kê âm vị (IPA heatmap).

Idempotent như các migration trước. wallets/user_items: Coins & Shop, Gacha, Hearts; guilds/guild_members: Study Clan
(mỗi user tối đa 1 bang); phoneme_stats: điểm trung bình từng âm IPA từ Azure Pronunciation Assessment.
"""

from alembic import op


revision = "20261023_0036"
down_revision = "20261012_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS wallets (
            user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            coins integer NOT NULL DEFAULT 0 CHECK (coins >= 0),
            hearts integer NOT NULL DEFAULT 5 CHECK (hearts >= 0),
            hearts_updated_at timestamptz NOT NULL DEFAULT now(),
            booster_until timestamptz
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_items (
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            item_id varchar(40) NOT NULL,
            equipped boolean NOT NULL DEFAULT false,
            acquired_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, item_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS guilds (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            name varchar(40) NOT NULL,
            join_code varchar(8) NOT NULL UNIQUE,
            owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_members (
            guild_id uuid NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
            user_id uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            joined_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (guild_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS phoneme_stats (
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            phoneme varchar(12) NOT NULL,
            attempts integer NOT NULL DEFAULT 0,
            total_score double precision NOT NULL DEFAULT 0,
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, phoneme)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS phoneme_stats")
    op.execute("DROP TABLE IF EXISTS guild_members")
    op.execute("DROP TABLE IF EXISTS guilds")
    op.execute("DROP TABLE IF EXISTS user_items")
    op.execute("DROP TABLE IF EXISTS wallets")
