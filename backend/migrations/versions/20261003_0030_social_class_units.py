"""Nhãn unit cho từ vựng, nhật ký giọng nói, bạn bè, lớp học + bài giao, hồ sơ phụ huynh (backlog 3.11, 4.4, 4.6, 5).

Idempotent như các migration trước; chỉ thêm cột/bảng mới, không đổi dữ liệu cũ.
"""

from alembic import op
from sqlalchemy import Column, SmallInteger, String, inspect
from sqlalchemy.dialects.postgresql import TIMESTAMP


revision = "20261003_0030"
down_revision = "20261003_0029"
branch_labels = None
depends_on = None


def _add_missing(table: str, columns: list[Column]) -> None:
    existing = {c["name"] for c in inspect(op.get_bind()).get_columns(table)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table, column)


def upgrade() -> None:
    _add_missing("vocab_items", [Column("unit_label", String(100), nullable=True)])
    op.execute("CREATE INDEX IF NOT EXISTS ix_vocab_items_user_unit ON vocab_items (user_id, unit_label)")

    # Năm sinh để biết dưới 18; email phụ huynh + thời điểm phụ huynh xác nhận bằng mã OTP.
    _add_missing(
        "users",
        [
            Column("birth_year", SmallInteger, nullable=True),
            Column("parent_email", String(255), nullable=True),
            Column("parent_consent_at", TIMESTAMP(timezone=True), nullable=True),
        ],
    )

    # auth_tokens.purpose có CHECK chỉ cho 2 giá trị: mở rộng thêm 'parent_consent'.
    op.execute(
        """
        DO $$
        DECLARE c text;
        BEGIN
            FOR c IN SELECT conname FROM pg_constraint
                     WHERE conrelid = 'auth_tokens'::regclass AND contype = 'c'
                       AND pg_get_constraintdef(oid) LIKE '%purpose%'
            LOOP
                EXECUTE format('ALTER TABLE auth_tokens DROP CONSTRAINT %I', c);
            END LOOP;
            ALTER TABLE auth_tokens ADD CONSTRAINT auth_tokens_purpose_check
                CHECK (purpose IN ('verify_email', 'reset_password', 'parent_consent'));
        END $$
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS voice_diary_entries (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            file_name varchar(100) NOT NULL,
            duration_seconds integer NOT NULL CHECK (duration_seconds BETWEEN 1 AND 120),
            transcript text,
            words_per_minute integer,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_voice_diary_user_created ON voice_diary_entries (user_id, created_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS friendships (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            requester_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            addressee_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status varchar(10) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted')),
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK (requester_id <> addressee_id),
            UNIQUE (requester_id, addressee_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_friendships_addressee ON friendships (addressee_id, status)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS classes (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            teacher_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name varchar(100) NOT NULL,
            join_code varchar(8) NOT NULL UNIQUE,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_classes_teacher ON classes (teacher_id)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS class_members (
            class_id uuid NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            joined_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (class_id, user_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_class_members_user ON class_members (user_id)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS class_assignments (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            class_id uuid NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            title varchar(150) NOT NULL,
            description text,
            skill varchar(20) CHECK (skill IN ('reading', 'listening', 'writing', 'speaking', 'vocab', 'grammar')),
            due_date date,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_class_assignments_class ON class_assignments (class_id, created_at DESC)")


def downgrade() -> None:
    """Giữ nguyên dữ liệu đã ghi; không xoá bảng/cột (đúng quy ước các migration trước)."""
