"""UNIQUE từ vựng theo user + CHECK cho skill_progress (thiet_ke_database.md mục 12.4).

- uq_vocab_items_user_term: mỗi user chỉ có 1 mục cho mỗi từ (không phân biệt hoa/thường). Dữ liệu
  đang có được gộp trước (giữ bản cũ nhất; vocab_reviews/custom_stories/contextual_guess trỏ tới
  bản bị gộp được chuyển sang bản giữ lại) để việc tạo index không thất bại.
- chk_skill_progress_skill_valid: skill_name chỉ là 4 kỹ năng mà gamification_service ghi.
Idempotent như các migration trước.
"""

from alembic import op


revision = "20260924_0016"
down_revision = "20260924_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bản trùng = cùng (user, lower(term)); giữ bản tạo sớm nhất.
    op.execute(
        """
        CREATE TEMP TABLE _vocab_dupes ON COMMIT DROP AS
        SELECT id AS dup_id,
               first_value(id) OVER (PARTITION BY user_id, lower(term) ORDER BY created_at, id) AS keep_id
        FROM vocab_items
        """
    )
    op.execute("DELETE FROM _vocab_dupes WHERE dup_id = keep_id")
    op.execute(
        "UPDATE contextual_guess_attempts c SET vocab_item_id = d.keep_id "
        "FROM _vocab_dupes d WHERE c.vocab_item_id = d.dup_id"
    )
    op.execute(
        "UPDATE custom_stories s SET vocab_item_ids = ("
        "SELECT array_agg(DISTINCT coalesce(d.keep_id, x)) FROM unnest(s.vocab_item_ids) AS x "
        "LEFT JOIN _vocab_dupes d ON d.dup_id = x) "
        "WHERE EXISTS (SELECT 1 FROM unnest(s.vocab_item_ids) AS x JOIN _vocab_dupes d ON d.dup_id = x)"
    )
    # vocab_reviews.vocab_item_id là UNIQUE + ON DELETE CASCADE: xoá bản trùng kéo theo review của nó.
    op.execute("DELETE FROM vocab_items WHERE id IN (SELECT dup_id FROM _vocab_dupes)")

    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_vocab_items_user_term ON vocab_items (user_id, lower(term))"
    )

    op.execute("ALTER TABLE skill_progress DROP CONSTRAINT IF EXISTS chk_skill_progress_skill_valid")
    op.execute(
        "ALTER TABLE skill_progress ADD CONSTRAINT chk_skill_progress_skill_valid "
        "CHECK (skill_name IN ('reading', 'listening', 'writing', 'speaking'))"
    )


def downgrade() -> None:
    """Không gộp ngược dữ liệu; chỉ bỏ ràng buộc mới."""
    op.execute("DROP INDEX IF EXISTS uq_vocab_items_user_term")
    op.execute("ALTER TABLE skill_progress DROP CONSTRAINT IF EXISTS chk_skill_progress_skill_valid")
