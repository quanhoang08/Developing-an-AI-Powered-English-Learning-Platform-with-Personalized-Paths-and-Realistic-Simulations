-- ============================================================================
-- LUMINA — schema.sql
-- Nền tảng học tiếng Anh ứng dụng AI (khóa luận tốt nghiệp)
--
-- Nguồn: thiet_ke_database.md (mục 1-9), đối chiếu de_cuong_khoa_luan.md,
-- feature-reading.md, feature-listening.md, feature-writing.md,
-- feature-speaking.md, api-spec.md, test-cases (1).md, erd_1.mermaid.
--
-- LƯU Ý QUAN TRỌNG:
--   - Đây là bản DDL đầu tiên được sinh cho project — trước đó chỉ có mô tả
--     văn xuôi (thiet_ke_database.md), CHƯA có schema.sql/ERD gốc dạng file.
--   - File này là "target schema" (trạng thái thiết kế cuối cùng đã biết tại
--     thời điểm viết), KHÔNG phải một chuỗi migration Alembic theo từng bước.
--     Khi implement thật, nên chuyển từng phần thành các revision Alembic
--     riêng theo đúng thứ tự Giai đoạn 1-8 (de_cuong_khoa_luan.md mục 8),
--     không chạy nguyên file này làm 1 migration duy nhất.
--   - Một số cột/kiểu dữ liệu là SUY LUẬN HỢP LÝ (không có trong mô tả gốc,
--     đánh dấu bằng comment "-- đề xuất"), cần xác nhận lại trước khi dùng
--     làm migration thật cho sản phẩm.
--   - 2 quyết định mới nhất (rà soát lần 3): reading_answers.passage_citation_ref
--     (thiet_ke_database.md mục 9.1), quizzes/quiz_attempts.quiz_id
--     (thiet_ke_database.md mục 9.2).
--   - 1 quyết định mới trong lần viết schema.sql này: writing_submissions.rubric_scores
--     + trigger tự động ghi user_errors(error_type='writing_coherence') khi điểm
--     Coherence & Cohesion dưới ngưỡng — xem phần "TRIGGERS" cuối file.
--   - CẬP NHẬT 2026-09-24 (migration 20260924_0015, thiet_ke_database.md mục 12):
--     nguồn DDL thực thi được DUY NHẤT là ../schema.sql (pg_dump DB thật). File
--     này giữ vai trò giải thích thiết kế; tên cột có thể khác bản thật
--     (session_id → reading_session_id, submission_id → writing_submission_id,
--     transcript text/start_ms → word_text/start_time_ms). Các điểm đã sửa cho
--     khớp DB thật: embedding/embedding_local + HNSW, bỏ passage_citation_ref,
--     nới CHECK vocab/writing, bỏ trigger writing_coherence (ghi ở service).
--   - Điểm còn mở KHÔNG xử lý trong file này (cần quyết định thêm, xem
--     lumina_context.md mục 4): tên đề tài chính thức, seed data slang_phrases,
--     việc Speaking đóng góp user_errors loại nào.
--
-- Quy ước chung áp dụng cho toàn bộ file:
--   - Khóa chính: uuid, DEFAULT gen_random_uuid().
--   - Timestamp: TIMESTAMPTZ (không dùng TIMESTAMP không timezone).
--   - Enum cố định: dùng Postgres native ENUM (không dùng VARCHAR + CHECK) —
--     đúng đề xuất migration đã ghi trong api-spec.md mục 9, áp dụng nhất
--     quán cho MỌI cột enum trong schema, không riêng error_type.
--   - Chính sách ON DELETE (giải quyết điểm mở #10, xem chi tiết từng bảng):
--       (a) FK -> users.id: luôn CASCADE (hỗ trợ xoá tài khoản kiểu GDPR,
--           đơn giản hoá cho phạm vi khóa luận).
--       (b) FK mà cột đó tham gia một ràng buộc CHECK dạng "XOR bắt buộc 1
--           trong 2" (vd reading_sessions, reading_answers, vocab_items,
--           movie_context_matches): CASCADE, để tránh vi phạm CHECK khi chỉ
--           SET NULL một vế (nếu app cần "xoá mềm" tài liệu mà vẫn giữ lịch
--           sử làm bài, đây là việc cần xử lý ở tầng ứng dụng/soft-delete,
--           không phải ở FK cứng này).
--           NGOẠI LỆ (2026-09-24, thiet_ke_database.md mục 12): vocab_items và
--           writing_submissions dùng SET NULL + CHECK đã nới ("không được có cả
--           2 nguồn" / "free_topic không có document"), vì từ vựng và bài viết
--           là dữ liệu học của user, không nên mất khi xoá tài liệu gốc.
--       (c) FK tới bảng "thư viện/tham chiếu dùng chung" (scenarios,
--           personas khi cột NOT NULL): RESTRICT, để không vô tình xoá mất
--           lịch sử người dùng chỉ vì xoá 1 dòng trong thư viện nội dung.
--       (d) FK optional thuần tuý, bản ghi con vẫn có ý nghĩa độc lập khi
--           NULL (persona_id nullable, quiz_id nullable, slang_phrase_id...):
--           SET NULL.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector, dùng cho document_chunks.embedding

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

CREATE TYPE cefr_level_enum AS ENUM ('a1', 'a2', 'b1', 'b2', 'c1', 'c2');

CREATE TYPE formality_level_enum AS ENUM ('casual', 'neutral', 'formal');

CREATE TYPE document_source_type_enum AS ENUM ('audio', 'docx');

CREATE TYPE document_status_enum AS ENUM ('processing', 'ready', 'failed');

CREATE TYPE reading_mode_enum AS ENUM ('classic', 'skim_scan');

CREATE TYPE story_length_enum AS ENUM ('short', 'medium');

CREATE TYPE writing_source_type_enum AS ENUM ('document_summary', 'extended_topic', 'free_topic');

CREATE TYPE certificate_style_enum AS ENUM ('toeic', 'ielts', 'cambridge');

CREATE TYPE writing_insight_type_enum AS ENUM ('grammar', 'vocabulary', 'style');

CREATE TYPE stt_provider_enum AS ENUM ('azure', 'whisper');

CREATE TYPE client_type_enum AS ENUM ('web', 'extension');

-- quiz_type_enum: danh sách có thể mở rộng khi Adaptive Engine thêm loại đề
-- mới (vd 'adaptive_dynamic') — hiện tại chỉ 3 giá trị đã có mô tả rõ trong
-- feature-reading.md/feature-writing.md/api-spec.md.
CREATE TYPE quiz_type_enum AS ENUM ('rearrange_reading', 'rearrange_writing', 'adaptive_dynamic');

-- error_type_enum: đề xuất trong api-spec.md mục 9 (9 giá trị) — vẫn ở trạng
-- thái "chưa chốt chính thức" theo lumina_context.md mục 4 điểm 1, dùng tạm
-- trong schema.sql này vì cần 1 kiểu cụ thể để viết DDL. writing_coherence
-- nay đã có flow ghi dữ liệu cụ thể (xem TRIGGERS cuối file).
CREATE TYPE error_type_enum AS ENUM (
    'grammar',
    'vocabulary',
    'spelling',
    'pronunciation',
    'listening_comprehension',
    'reading_comprehension',
    'writing_coherence',
    'communicative_intent',
    'politeness'
);

CREATE TYPE review_source_type_enum AS ENUM ('vocab_review', 'user_error');

CREATE TYPE skill_enum AS ENUM ('reading', 'listening', 'writing', 'speaking');

CREATE TYPE movie_context_source_type_enum AS ENUM ('real_video', 'tts_fallback');


-- ============================================================================
-- CORE (tier: Đầy đủ / MVP)
-- ============================================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,                     -- bcrypt qua passlib
    target_level    cefr_level_enum NOT NULL DEFAULT 'b1',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE notebook_folders (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    folder_id       UUID REFERENCES notebook_folders(id) ON DELETE SET NULL,
    source_type     document_source_type_enum NOT NULL,
    status          document_status_enum NOT NULL DEFAULT 'processing',
    tags            JSONB NOT NULL DEFAULT '[]'::jsonb,
    starred         BOOLEAN NOT NULL DEFAULT false,
    file_size_kb    INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content         TEXT NOT NULL,
    embedding       vector(768),                       -- gemini-embedding-001 (EMBEDDING_PROVIDER=gemini)
    embedding_local vector(1024),                      -- bge-m3 qua Ollama (EMBEDDING_PROVIDER=ollama, mặc định)
    chunk_index     INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE generated_passages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic       TEXT NOT NULL,
    level       cefr_level_enum NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================================
-- MODULE 1 — READING & VOCAB (tier: Đầy đủ; Rearrange = Thử nghiệm giới hạn)
-- ============================================================================

CREATE TABLE reading_sessions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id             UUID REFERENCES documents(id) ON DELETE CASCADE,
    generated_passage_id    UUID REFERENCES generated_passages(id) ON DELETE CASCADE,
    mode                    reading_mode_enum NOT NULL,
    score                   NUMERIC(4,2),
    completed_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_reading_sessions_source_xor CHECK (
        (mode = 'classic'    AND document_id IS NOT NULL AND generated_passage_id IS NULL)
        OR
        (mode = 'skim_scan'  AND generated_passage_id IS NOT NULL AND document_id IS NULL)
    )
);

CREATE TABLE reading_answers (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id                  UUID NOT NULL REFERENCES reading_sessions(id) ON DELETE CASCADE,
    options                     JSONB NOT NULL,
    correct_option_index        INTEGER NOT NULL,
    selected_option_index       INTEGER,
    -- source_chunk_id chỉ set cho Classic Mode. Skim & Scan hiện KHÔNG lưu trích
    -- dẫn (câu hỏi do LLM sinh không kèm vị trí) — passage_citation_ref + CHECK XOR
    -- ở mục 9.1 chưa implement, xem thiet_ke_database.md mục 12.
    source_chunk_id             UUID REFERENCES document_chunks(id) ON DELETE SET NULL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vocab_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    term            TEXT NOT NULL,
    definition      TEXT NOT NULL,
    synonyms        JSONB NOT NULL DEFAULT '[]'::jsonb,
    antonyms        JSONB NOT NULL DEFAULT '[]'::jsonb,
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    source_url      TEXT,                               -- tier Thử nghiệm giới hạn (Browser Extension)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Chỉ cấm có cả 2 nguồn: document_id về NULL khi xoá tài liệu (SET NULL), từ vựng
    -- vẫn giữ lại. "Đúng 1 nguồn khi tạo" được validate ở API (schemas/vocab.py).
    CONSTRAINT chk_vocab_items_source_xor CHECK (
        NOT (document_id IS NOT NULL AND source_url IS NOT NULL)
    )
);

CREATE TABLE vocab_reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vocab_item_id   UUID NOT NULL UNIQUE REFERENCES vocab_items(id) ON DELETE CASCADE,  -- quan hệ 1-1
    ease_factor     NUMERIC(4,2) NOT NULL DEFAULT 2.50 CHECK (ease_factor >= 1.3),
    interval_days   INTEGER NOT NULL DEFAULT 0,
    repetitions     INTEGER NOT NULL DEFAULT 0,
    next_review_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE contextual_guess_attempts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vocab_item_id           UUID REFERENCES vocab_items(id) ON DELETE SET NULL,
    term                    TEXT NOT NULL,                -- luôn có giá trị, độc lập vocab_item_id
    challenge_sentence      TEXT NOT NULL,
    options                 JSONB NOT NULL,
    correct_option_index    INTEGER NOT NULL,
    selected_option_index   INTEGER,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE custom_stories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vocab_item_ids  JSONB NOT NULL,                       -- mảng uuid, không enforce FK (xem ghi chú cuối file)
    content         TEXT NOT NULL,
    theme           TEXT,
    length          story_length_enum NOT NULL DEFAULT 'short',
    missing_terms   JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================================
-- PERSONAS (dùng chung Podcast / Speaking / Movie Context) — tier: Đầy đủ
-- ============================================================================

CREATE TABLE personas (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    voice_id    TEXT NOT NULL,               -- id giọng bên ElevenLabs
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================================
-- MODULE 2 — LISTENING (tier: Đầy đủ)
-- ============================================================================

CREATE TABLE podcasts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    persona_id      UUID REFERENCES personas(id) ON DELETE SET NULL,   -- fallback persona mặc định nếu NULL
    audio_url       TEXT NOT NULL,
    status          document_status_enum NOT NULL DEFAULT 'processing',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE transcript_segments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    podcast_id  UUID NOT NULL REFERENCES podcasts(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    start_ms    INTEGER NOT NULL,
    end_ms      INTEGER NOT NULL,
    CONSTRAINT chk_transcript_segments_range CHECK (end_ms > start_ms)
);

CREATE TABLE dictation_attempts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    podcast_id              UUID NOT NULL REFERENCES podcasts(id) ON DELETE CASCADE,
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    start_ms                INTEGER NOT NULL,
    end_ms                  INTEGER NOT NULL,
    reference_word_tags     JSONB NOT NULL DEFAULT '[]'::jsonb,  -- vd [{"word":"mitochondria","is_rare_or_proper":true}]
    transcribed_text        TEXT,
    score                   NUMERIC(4,2),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================================
-- MODULE 3 — WRITING (tier: Đầy đủ; Rearrange = Thử nghiệm giới hạn)
-- ============================================================================

CREATE TABLE writing_submissions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id         UUID REFERENCES documents(id) ON DELETE CASCADE,
    source_type         writing_source_type_enum NOT NULL,
    prompt_text         TEXT NOT NULL,
    certificate_style   certificate_style_enum,
    submitted_text      TEXT,
    -- rubric_scores: MỚI (quyết định trong lúc viết schema.sql, xem đầu file
    -- và TRIGGERS cuối file) — chỉ dùng cho extended_topic/free_topic (rubric
    -- 4 tiêu chí), NULL với document_summary (chấm theo coverage, không có
    -- 4 tiêu chí này).
    -- Hình dạng đề xuất: {"task_response": int, "coherence_cohesion": int,
    --                      "lexical_resource": int, "grammatical_range_accuracy": int}
    -- mỗi tiêu chí thang 0-100, cùng thang với intent_score/politeness_score
    -- của Speaking để nhất quán trong toàn hệ thống.
    rubric_scores       JSONB,
    cefr_level          cefr_level_enum,
    ielts_band          NUMERIC(2,1),
    score               NUMERIC(5,2),
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Giải quyết điểm mở #11 (chính sách CHECK chưa nhất quán): trước đây
    -- ràng buộc document_id theo source_type chỉ được validate ở tầng service
    -- (thiet_ke_database.md mục 7). Nay áp CHECK ở DB để nhất quán với cách
    -- đã làm ở reading_sessions/vocab_items/reading_answers.
    -- Cập nhật 2026-09-24: bỏ yêu cầu document_id NOT NULL cho document_summary/
    -- extended_topic — nó xung đột với FK ON DELETE SET NULL làm DELETE documents
    -- bị chặn. Service bắt document khi tạo đề; submit trả 404 nếu tài liệu đã xoá.
    CONSTRAINT chk_writing_submissions_source_type CHECK (
        source_type <> 'free_topic' OR document_id IS NULL
    ),
    -- Formal hoá acceptance criteria đã có ở feature-writing.md mục 1.6:
    -- cefr_level/ielts_band luôn có giá trị khi bài đã chấm xong.
    CONSTRAINT chk_writing_submissions_graded_complete CHECK (
        completed_at IS NULL OR (cefr_level IS NOT NULL AND ielts_band IS NOT NULL)
    ),
    -- rubric_scores bắt buộc khi bài extended_topic/free_topic đã chấm xong;
    -- luôn NULL với document_summary (chấm theo coverage, không dùng rubric này).
    CONSTRAINT chk_writing_submissions_rubric CHECK (
        (source_type = 'document_summary' AND rubric_scores IS NULL)
        OR
        (source_type <> 'document_summary' AND (completed_at IS NULL OR rubric_scores IS NOT NULL))
    )
);

CREATE TABLE writing_insights (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id   UUID NOT NULL REFERENCES writing_submissions(id) ON DELETE CASCADE,
    insight_type    writing_insight_type_enum NOT NULL,
    offset_start    INTEGER,          -- chỉ set khi insight_type = 'grammar', tính theo ký tự UTF-8
    offset_end      INTEGER,
    original_text   TEXT,
    suggested_text  TEXT,
    explanation     TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_writing_insights_offset CHECK (
        (insight_type = 'grammar' AND offset_start IS NOT NULL AND offset_end IS NOT NULL AND offset_end > offset_start)
        OR
        (insight_type <> 'grammar' AND offset_start IS NULL AND offset_end IS NULL)
    )
);

CREATE TABLE rephrase_requests (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id           UUID NOT NULL REFERENCES writing_submissions(id) ON DELETE CASCADE,
    original_sentence       TEXT NOT NULL,
    suggested_sentences     JSONB NOT NULL,     -- [{"text": string, "explanation": string}]
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================================
-- MODULE 4 — SPEAKING (tier: Thử nghiệm giới hạn)
-- ============================================================================

CREATE TABLE scenarios (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    description         TEXT NOT NULL,
    goal                TEXT NOT NULL,                              -- feature-speaking.md 3.3
    formality_level     formality_level_enum NOT NULL DEFAULT 'neutral',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE conversation_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scenario_id         UUID NOT NULL REFERENCES scenarios(id) ON DELETE RESTRICT,
    persona_id          UUID REFERENCES personas(id) ON DELETE SET NULL,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE conversation_turns (
    id                                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id                          UUID NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    transcription                       TEXT NOT NULL,
    response_text                       TEXT NOT NULL,
    pronunciation_score                 INTEGER CHECK (pronunciation_score BETWEEN 0 AND 100),
    pronunciation_assessment_failed     BOOLEAN NOT NULL DEFAULT false,
    intent_score                        INTEGER CHECK (intent_score BETWEEN 0 AND 100),          -- đề xuất, chưa chốt rubric
    intent_feedback                     TEXT,
    politeness_score                    INTEGER CHECK (politeness_score BETWEEN 0 AND 100),       -- đề xuất, chưa chốt rubric
    politeness_feedback                 TEXT,
    stt_provider_used                   stt_provider_enum NOT NULL,
    suggested_phrases                   JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at                          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE slang_phrases (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phrase_text         TEXT NOT NULL,
    meaning             TEXT NOT NULL,
    example_sentence    TEXT NOT NULL,
    formality_level     formality_level_enum NOT NULL,
    source_reference    TEXT NOT NULL,          -- tên nguồn, phục vụ trích dẫn học thuật
    topic_tags          JSONB NOT NULL DEFAULT '[]'::jsonb,   -- đề xuất, chưa chốt (feature-speaking.md 4.1)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_phrasebook_entries (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slang_phrase_id             UUID REFERENCES slang_phrases(id) ON DELETE SET NULL,
    conversation_turn_id        UUID REFERENCES conversation_turns(id) ON DELETE SET NULL,
    phrase_text                 TEXT,      -- snapshot, dùng khi slang_phrase_id NULL (LLM sinh tại chỗ)
    meaning                     TEXT,
    example_sentence            TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_phrasebook_has_content CHECK (
        slang_phrase_id IS NOT NULL OR phrase_text IS NOT NULL
    )
);

-- Định hướng mở rộng (FUT) — để trống cho tới khi nâng cấp streaming thời gian thực.
CREATE TABLE realtime_conversation_metrics (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_turn_id    UUID NOT NULL REFERENCES conversation_turns(id) ON DELETE CASCADE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================================
-- MODULE 0 — ADAPTIVE LEARNING ENGINE (tier: Đầy đủ)
-- ============================================================================

-- quizzes: quyết định rà soát lần 3 (thiet_ke_database.md mục 9.2) — CHỈ dành
-- cho đề động do /api/adaptive/quizzes/generate sinh. Rearrange the Block
-- KHÔNG tạo dòng quizzes, ghi thẳng quiz_attempts (quiz_id = NULL).
CREATE TABLE quizzes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- Các lỗi (user_errors.id) làm nguồn sinh đề; không có FK vì là mảng (Postgres không hỗ trợ FK theo phần tử).
    generated_from_error_ids UUID[],
    focus_error_types   JSONB,              -- mảng error_type_enum dạng text, nullable
    -- Mỗi câu: { question_text, options[], correct_option_index, explanation, error_id, error_type }.
    -- API chỉ trả question_text/options/error_type cho client; đáp án chỉ trả sau khi nộp bài.
    questions           JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE quiz_attempts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quiz_id         UUID REFERENCES quizzes(id) ON DELETE SET NULL,   -- chỉ set cho Adaptive Engine
    quiz_type       quiz_type_enum NOT NULL,
    is_open_form    BOOLEAN,            -- chỉ có ý nghĩa cho quiz_type = 'rearrange_writing'
    answers         JSONB,              -- Adaptive quiz: mảng chỉ số đáp án đã chọn, đúng thứ tự câu hỏi
    score           NUMERIC(5,2),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_quiz_attempts_open_form CHECK (
        (quiz_type = 'rearrange_writing') OR (is_open_form IS NULL)
    )
);

CREATE TABLE user_errors (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quiz_attempt_id             UUID REFERENCES quiz_attempts(id) ON DELETE SET NULL,
    error_type                  error_type_enum NOT NULL,
    spaced_repetition_level     INTEGER NOT NULL DEFAULT 0,
    -- Nội dung lỗi cụ thể để sinh câu hỏi luyện đúng lỗi:
    -- { source, original_text?, corrected_text?, explanation? }; NULL với lỗi cũ chỉ có error_type.
    detail                      JSONB,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- review_priority_queue.source_id là tham chiếu đa hình (vocab_reviews.id
-- hoặc user_errors.id tùy source_type) — KHÔNG enforce bằng FK cứng trong
-- Postgres thuần (cần 2 FK nullable riêng hoặc kiểm tra ở tầng ứng dụng).
-- Giữ nguyên thiết kế đa hình đơn giản theo đúng mô tả gốc, ghi chú rõ đây
-- là giới hạn đã biết, không phải thiếu sót.
-- LƯU Ý (khác biệt với DB thật, xem ../schema.sql): bảng thật dùng item_type
-- VARCHAR(20) ('vocab' | 'error'), item_id, priority_score NUMERIC(6,2) và
-- last_calculated_at thay cho source_type/source_id/priority_score(6,3)/created_at;
-- backend tính lại toàn bộ hàng đợi mỗi lần đọc (priority_queue_service.py).
CREATE TABLE review_priority_queue (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type     review_source_type_enum NOT NULL,
    source_id       UUID NOT NULL,          -- xem ghi chú trên: không có FK cứng
    priority_score  NUMERIC(6,3) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE streaks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    current_streak      INTEGER NOT NULL DEFAULT 0,
    longest_streak      INTEGER NOT NULL DEFAULT 0,
    last_active_date    DATE,
    total_xp            INTEGER NOT NULL DEFAULT 0   -- XP tích luỹ (Gamification, migration 20260920_0012)
);

CREATE TABLE skill_progress (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill       skill_enum NOT NULL,           -- DB thật: skill_name VARCHAR(30) + CHECK 4 kỹ năng (migration 0016)
    cefr_level  cefr_level_enum,               -- chỉ writing có giá trị (LLM ước lượng)
    score       NUMERIC(5,2),                  -- trung bình động 0-100 (gamification_service.record_skill_score)
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, skill)
);


-- ============================================================================
-- AUTH / BROWSER EXTENSION (tier: Đầy đủ + Thử nghiệm giới hạn)
-- ============================================================================

CREATE TABLE refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL UNIQUE,
    -- Giải quyết điểm mở #13 (phạm vi token Extension): quyết định — token
    -- client_type='extension' CHỈ được phép gọi /api/extension/* +
    -- /api/reading/lookup + /api/vocab (không gọi được các route web khác).
    -- Đây là chính sách TĨNH (giống nhau cho mọi token extension), nên KHÔNG
    -- cần thêm cột riêng ở đây — enforce bằng middleware đọc client_type và
    -- so với allow-list route cố định (không phải logic thuộc tầng DB).
    -- TODO (ngoài phạm vi DB): viết middleware kiểm tra scope này trước khi
    -- extension đi vào code thật (auth dependency trong FastAPI, áp dụng
    -- cho mọi router ngoài allow-list).
    client_type     client_type_enum NOT NULL DEFAULT 'web',
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked         BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================================
-- MODULE 5 — MOVIE DELIVERY CONTEXT (tier: Thử nghiệm giới hạn + Định hướng mở rộng)
-- ============================================================================

CREATE TABLE movie_context_tts_fallback (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phrase_text     TEXT NOT NULL,
    audio_url       TEXT NOT NULL,
    persona_id      UUID NOT NULL REFERENCES personas(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Định hướng mở rộng (FUT) — video_sources/video_subtitle_index CHƯA build
-- trong phạm vi khóa luận. Được tạo sẵn ở đây (giải quyết điểm mở #12) để
-- movie_context_matches.source_type = 'real_video' có FK hợp lệ ngay từ đầu,
-- tránh phải ALTER thêm giá trị enum/FK khi làm nhánh video thật sau này.
-- KHÔNG có nghĩa là nhánh này được implement — chỉ là chuẩn bị sẵn schema.
CREATE TABLE video_sources (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       TEXT NOT NULL,
    url         TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE video_subtitle_index (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_source_id     UUID NOT NULL REFERENCES video_sources(id) ON DELETE CASCADE,
    phrase              TEXT NOT NULL,
    timestamp_ms        INTEGER NOT NULL
);

CREATE TABLE movie_context_matches (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phrase                      TEXT NOT NULL,
    source_type                 movie_context_source_type_enum NOT NULL,
    tts_fallback_id             UUID REFERENCES movie_context_tts_fallback(id) ON DELETE CASCADE,
    video_subtitle_index_id     UUID REFERENCES video_subtitle_index(id) ON DELETE CASCADE,
    is_saved                    BOOLEAN NOT NULL DEFAULT false,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_movie_context_matches_source_xor CHECK (
        (source_type = 'tts_fallback' AND tts_fallback_id IS NOT NULL AND video_subtitle_index_id IS NULL)
        OR
        (source_type = 'real_video'   AND video_subtitle_index_id IS NOT NULL AND tts_fallback_id IS NULL)
    )
);


-- ============================================================================
-- INDEXES
-- ============================================================================

-- FK lookups (Postgres không tự tạo index cho FK)
CREATE INDEX idx_notebook_folders_user_id ON notebook_folders(user_id);
CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_folder_id ON documents(folder_id);
CREATE INDEX idx_documents_tags ON documents USING GIN (tags);
CREATE INDEX idx_document_chunks_document_id ON document_chunks(document_id);
-- HNSW: không cần tinh chỉnh list count như ivfflat, phù hợp quy mô khóa luận
CREATE INDEX idx_document_chunks_embedding ON document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_document_chunks_embedding_local ON document_chunks USING hnsw (embedding_local vector_cosine_ops);
CREATE INDEX idx_generated_passages_user_id ON generated_passages(user_id);

CREATE INDEX idx_reading_sessions_user_id ON reading_sessions(user_id);
CREATE INDEX idx_reading_sessions_document_id ON reading_sessions(document_id);
CREATE INDEX idx_reading_sessions_generated_passage_id ON reading_sessions(generated_passage_id);
CREATE INDEX idx_reading_answers_session_id ON reading_answers(session_id);
CREATE INDEX idx_reading_answers_source_chunk_id ON reading_answers(source_chunk_id);

CREATE UNIQUE INDEX uq_vocab_items_user_term ON vocab_items(user_id, lower(term));  -- migration 0016; API trả 409
CREATE INDEX idx_vocab_items_user_id ON vocab_items(user_id);
CREATE INDEX idx_vocab_items_document_id ON vocab_items(document_id);
CREATE INDEX idx_vocab_reviews_next_review_at ON vocab_reviews(next_review_at);
CREATE INDEX idx_contextual_guess_attempts_user_id ON contextual_guess_attempts(user_id);
CREATE INDEX idx_contextual_guess_attempts_vocab_item_id ON contextual_guess_attempts(vocab_item_id);
CREATE INDEX idx_custom_stories_user_id ON custom_stories(user_id);

CREATE INDEX idx_podcasts_document_id ON podcasts(document_id);
CREATE INDEX idx_podcasts_persona_id ON podcasts(persona_id);
CREATE INDEX idx_transcript_segments_podcast_id ON transcript_segments(podcast_id);
CREATE INDEX idx_dictation_attempts_podcast_id ON dictation_attempts(podcast_id);
CREATE INDEX idx_dictation_attempts_user_id ON dictation_attempts(user_id);

CREATE INDEX idx_writing_submissions_user_id ON writing_submissions(user_id);
CREATE INDEX idx_writing_submissions_document_id ON writing_submissions(document_id);
CREATE INDEX idx_writing_insights_submission_id ON writing_insights(submission_id);
CREATE INDEX idx_rephrase_requests_submission_id ON rephrase_requests(submission_id);

CREATE INDEX idx_conversation_sessions_user_id ON conversation_sessions(user_id);
CREATE INDEX idx_conversation_sessions_scenario_id ON conversation_sessions(scenario_id);
CREATE INDEX idx_conversation_turns_session_id ON conversation_turns(session_id);
CREATE INDEX idx_user_phrasebook_entries_user_id ON user_phrasebook_entries(user_id);
CREATE INDEX idx_user_phrasebook_entries_slang_phrase_id ON user_phrasebook_entries(slang_phrase_id);
CREATE INDEX idx_user_phrasebook_entries_conversation_turn_id ON user_phrasebook_entries(conversation_turn_id);

CREATE INDEX idx_quizzes_user_id ON quizzes(user_id);
CREATE INDEX idx_quiz_attempts_user_id_created_at ON quiz_attempts(user_id, created_at DESC);
CREATE INDEX idx_quiz_attempts_quiz_id ON quiz_attempts(quiz_id);
CREATE INDEX idx_user_errors_user_id_error_type ON user_errors(user_id, error_type);
CREATE INDEX idx_user_errors_quiz_attempt_id ON user_errors(quiz_attempt_id);
CREATE INDEX idx_review_priority_queue_user_id ON review_priority_queue(user_id, priority_score DESC);
CREATE INDEX idx_skill_progress_user_id ON skill_progress(user_id);

CREATE INDEX idx_refresh_tokens_user_id_client_type ON refresh_tokens(user_id, client_type);

CREATE INDEX idx_movie_context_matches_phrase ON movie_context_matches(phrase);
CREATE INDEX idx_video_subtitle_index_video_source_id ON video_subtitle_index(video_source_id);
CREATE INDEX idx_video_subtitle_index_phrase ON video_subtitle_index(phrase);


-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- vocab_reviews.updated_at — cập nhật tự động mỗi lần review (SM-2).
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_vocab_reviews_updated_at
    BEFORE UPDATE ON vocab_reviews
    FOR EACH ROW
    EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_skill_progress_updated_at
    BEFORE UPDATE ON skill_progress
    FOR EACH ROW
    EXECUTE FUNCTION fn_set_updated_at();

-- Giải quyết điểm mở #9 (writing_coherence "mồ côi"): khi 1 bài
-- extended_topic/free_topic vừa được chấm xong (completed_at chuyển từ NULL
-- sang có giá trị) và điểm Coherence & Cohesion trong rubric_scores dưới
-- ngưỡng, tự động ghi 1 dòng user_errors(error_type='writing_coherence').
-- Ngưỡng đề xuất: < 60/100 — cùng logic phân dải điểm đã dùng cho
-- intent_score/politeness_score ở Speaking (feature-speaking.md mục 3.1:
-- 60-89 = "về cơ bản phù hợp", dưới 60 bắt đầu coi là có vấn đề rõ rệt) —
-- ĐÂY LÀ NGƯỠNG ĐỀ XUẤT, cần xác nhận lại giống các đề xuất khác của module
-- Adaptive Learning Engine trước khi chạy migration thật.
-- ĐÃ BỎ trigger (2026-09-24): writing_service.submit_essay ghi user_errors('writing_coherence')
-- bằng adaptive_service.record_error, kèm detail {source, submission_id, coherence_cohesion}.


-- ============================================================================
-- GHI CHÚ CUỐI FILE
-- ============================================================================
-- 1. custom_stories.vocab_item_ids và quizzes.focus_error_types là JSONB chứa
--    danh sách id/enum, KHÔNG enforce bằng FK — giới hạn đã biết của thiết kế
--    gốc (mảng trong 1 cột), chấp nhận được ở quy mô khóa luận. Nếu cần toàn
--    vẹn tham chiếu chặt hơn, chuyển thành bảng nối (junction table) — ngoài
--    phạm vi rà soát lần này.
-- 2. review_priority_queue.source_id là tham chiếu đa hình, không có FK cứng
--    — xem ghi chú tại chỗ định nghĩa bảng.
-- 3. error_type_enum, quiz_type_enum vẫn ở trạng thái "đề xuất, chưa chốt
--    chính thức" theo lumina_context.md mục 4 — dùng tạm trong file này vì
--    cần kiểu cụ thể để viết được DDL; đừng chạy migration thật cho đến khi
--    xác nhận lại.
-- ============================================================================
