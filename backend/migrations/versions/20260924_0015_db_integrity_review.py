"""Rà soát toàn vẹn DB (thiet_ke_database.md mục 12): sửa ràng buộc chặn xoá document, index vector,
dọn bảng cũ, index FK, UNIQUE/CHECK còn thiếu.

1. Xoá document bị chặn: vocab_items/writing_submissions.document_id là ON DELETE SET NULL nhưng CHECK
   lại bắt document_id NOT NULL → DELETE documents lỗi. Giữ SET NULL (không mất từ vựng/bài viết của
   user), nới CHECK: vocab chỉ cấm có cả 2 nguồn (API vẫn bắt đúng 1 nguồn khi tạo — schemas/vocab.py);
   writing chỉ cấm free_topic có document (service bắt document khi tạo đề).
2. Vector index: HNSW cho embedding_local (provider mặc định, trước đó không có index) và thay ivfflat
   (tạo lúc bảng rỗng, recall kém) bằng HNSW cho embedding.
3. Xoá error_log/accents (bảng cũ, 0 dòng, không code nào dùng).
4. FK: reading_answers.source_chunk_id → SET NULL; dictation_attempts.podcast_id → CASCADE + NOT NULL
   (khớp model; attempt không có podcast không dùng lại được).
5. Index cho FK có ON DELETE (xoá document/podcast không phải quét tuần tự bảng con).
6. UNIQUE (podcast_id, word_index), (conversation_session_id, turn_index).
7. CHECK cho các cột enum dạng chuỗi còn thiếu (giá trị đã đối chiếu với code và dữ liệu thật).

Idempotent như các migration trước: DROP ... IF EXISTS rồi tạo lại, CREATE INDEX IF NOT EXISTS.
"""

from alembic import op


revision = "20260924_0015"
down_revision = "20260924_0014"
branch_labels = None
depends_on = None


def _replace_check(table: str, name: str, expression: str) -> None:
    op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
    op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({expression})")


def _replace_fk(table: str, name: str, column: str, target: str, on_delete: str) -> None:
    op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY ({column}) "
        f"REFERENCES {target}(id) ON DELETE {on_delete}"
    )


_FK_INDEXES = {
    "idx_reading_sessions_document": ("reading_sessions", "document_id"),
    "idx_reading_sessions_passage": ("reading_sessions", "generated_passage_id"),
    "idx_reading_answers_source_chunk": ("reading_answers", "source_chunk_id"),
    "idx_vocab_document": ("vocab_items", "document_id"),
    "idx_contextual_guess_vocab_item": ("contextual_guess_attempts", "vocab_item_id"),
    "idx_writing_submissions_document": ("writing_submissions", "document_id"),
    "idx_podcasts_document": ("podcasts", "document_id"),
    "idx_dictation_attempts_podcast": ("dictation_attempts", "podcast_id"),
    "idx_user_errors_quiz_attempt": ("user_errors", "quiz_attempt_id"),
    "idx_phrasebook_user": ("user_phrasebook_entries", "user_id"),
    "idx_phrasebook_slang_phrase": ("user_phrasebook_entries", "slang_phrase_id"),
    "idx_phrasebook_conversation_turn": ("user_phrasebook_entries", "conversation_turn_id"),
}


def upgrade() -> None:
    # 1. Nới CHECK để ON DELETE SET NULL từ documents không bị chặn.
    _replace_check(
        "vocab_items",
        "chk_vocab_source_exactly_one",
        "NOT (document_id IS NOT NULL AND source_url IS NOT NULL)",
    )
    _replace_check(
        "writing_submissions",
        "chk_writing_document_id_by_source",
        "source_type <> 'free_topic' OR document_id IS NULL",
    )

    # 2. Vector index HNSW.
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_embedding_local_hnsw "
        "ON document_chunks USING hnsw (embedding_local vector_cosine_ops)"
    )

    # 3. Bảng cũ.
    op.execute("DROP TABLE IF EXISTS accents")
    op.execute("DROP TABLE IF EXISTS error_log")

    # 4. Quy tắc ON DELETE.
    _replace_fk(
        "reading_answers", "reading_answers_source_chunk_id_fkey", "source_chunk_id", "document_chunks", "SET NULL"
    )
    _replace_fk("dictation_attempts", "dictation_attempts_podcast_id_fkey", "podcast_id", "podcasts", "CASCADE")
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM dictation_attempts WHERE podcast_id IS NULL) THEN "
        "ALTER TABLE dictation_attempts ALTER COLUMN podcast_id SET NOT NULL; END IF; END $$"
    )

    # 5. Index FK.
    for name, (table, column) in _FK_INDEXES.items():
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({column})")

    # 6. UNIQUE tự nhiên.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_transcript_segments_podcast_word "
        "ON transcript_segments (podcast_id, word_index)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_conversation_turns_session_turn "
        "ON conversation_turns (conversation_session_id, turn_index)"
    )

    # 7. CHECK enum.
    _replace_check("documents", "chk_documents_source_type_valid", "source_type IN ('audio', 'docx')")
    _replace_check("documents", "chk_documents_status_valid", "status IN ('processing', 'ready', 'failed')")
    _replace_check("podcasts", "chk_podcasts_status_valid", "status IN ('processing', 'ready', 'failed')")
    _replace_check(
        "quiz_attempts",
        "chk_quiz_attempts_attempt_type_valid",
        "attempt_type IS NULL OR attempt_type IN ('rearrange_reading', 'rearrange_writing')",
    )
    _replace_check(
        "conversation_sessions",
        "chk_conversation_sessions_status_valid",
        "status IN ('in_progress', 'completed', 'expired')",
    )
    _replace_check(
        "writing_insights", "chk_writing_insights_type_valid", "insight_type IN ('grammar', 'vocabulary', 'style')"
    )
    _replace_check("review_priority_queue", "chk_review_priority_item_type_valid", "item_type IN ('vocab', 'error')")


def downgrade() -> None:
    """Không khôi phục CHECK cũ (chính chúng chặn xoá document) và bảng cũ đã bỏ."""
    pass
