-- ============================================================================
-- LUMINA — schema.sql
-- Nền tảng học tiếng Anh ứng dụng AI (khóa luận tốt nghiệp)
--
-- LƯU Ý QUAN TRỌNG:
--   - ĐỐI CHIẾU TOÀN DIỆN VỚI DB THẬT HOÀN TẤT (2026-09-27, lumina_context.md
--     mục 4 điểm 12). File này trước đây là "target schema" viết trước khi
--     code, đã lệch khá nhiều so với DB thật sau nhiều migration Alembic nối
--     tiếp nhau không đồng bộ ngược lại đây. Bản này được sinh lại bằng cách
--     `pg_dump --schema-only` trên `lumina_db` thật rồi diễn giải lại theo
--     đúng cấu trúc cột/constraint thật — không còn là "thiết kế mục tiêu"
--     nữa mà là **ảnh chụp DB thật, có annotate rationale**. Nguồn thực thi
--     được vẫn luôn là `../schema.sql` (root, sinh trực tiếp bằng pg_dump).
--   - 3 khác biệt lớn nhất so với bản thiết kế gốc (đáng nhớ khi bảo vệ khóa luận):
--     1. KHÔNG có bảng/cột nào dùng Postgres native ENUM (`CREATE TYPE ... AS ENUM`)
--        — quyết định thiết kế ban đầu (áp dụng enum cho mọi cột dạng enum)
--        chưa từng được thực thi. Toàn bộ dùng `VARCHAR(n) + CHECK (col IN (...))`,
--        nhất quán trong suốt quá trình implement thật (không phải thiếu sót
--        rải rác) — xem mục 4 điểm 8 lumina_context.md, cùng loại quyết định
--        "gọi thẳng google-generativeai, không qua LangChain".
--     2. Bảng `notebook_chat_messages` (RAG Chat, mục 3.12 lumina_context.md)
--        tồn tại thật trong DB nhưng CHƯA từng được thêm vào file này — đã bổ
--        sung ở phần MODULE NOTEBOOK / RAG CHAT dưới.
--     3. Nhiều bảng có thêm cột "tiện dụng cho UI" phát sinh trực tiếp lúc code
--        (không nằm trong thiết kế gốc) — vd `documents.title/source_url/file_path`,
--        `generated_passages.title/read_time_label/word_count_label`,
--        `podcasts.script_text`, `writing_insights.title/description`. Đây là
--        bổ sung hợp lý trong lúc implement, không phải lỗi — được giữ nguyên
--        và đánh dấu rõ trong từng bảng.
--   - Điểm mở KHÔNG xử lý trong lần đối chiếu này (không đổi so với trước, xem
--     lumina_context.md mục 4): tên đề tài chính thức, seed data slang_phrases,
--     ý nghĩa "cambridge" style, rubric điểm ý định/lịch sự.
--
-- Quy ước chung của DB thật (khác quy ước thiết kế gốc ở mục ENUM):
--   - Khóa chính: uuid, DEFAULT public.uuid_generate_v4() (extension uuid-ossp,
--     KHÔNG dùng gen_random_uuid()/pgcrypto như bản thiết kế gốc từng viết).
--   - Timestamp: timestamp with time zone (TIMESTAMPTZ) — đúng quy ước gốc.
--   - "Enum": VARCHAR(n) + CHECK constraint tên `chk_<table>_<col>_valid`,
--     KHÔNG dùng CREATE TYPE (xem điểm 1 trên).
--   - Chính sách ON DELETE thực tế — về cơ bản khớp với 4 nguyên tắc thiết kế
--     gốc (a: users→CASCADE; b: cặp CHECK "XOR 1-trong-2"→CASCADE hoặc SET
--     NULL+CHECK nới; d: FK optional thuần túy→SET NULL), NHƯNG có vài ngoại
--     lệ thật không theo đúng nguyên tắc, ghi rõ tại từng bảng:
--       * `quiz_attempts.quiz_id` → thiết kế gốc nói SET NULL (nguyên tắc d),
--         DB thật là **CASCADE** (xoá quiz kéo theo xoá luôn các lượt làm bài
--         thuộc quiz đó — hợp lý hơn SET NULL vì quiz_id NULL đang được dùng
--         để đánh dấu "không thuộc bộ đề nào" cho Rearrange, xoá mà giữ lại
--         attempt "mồ côi" theo kiểu Adaptive Engine dễ gây nhầm lẫn ngữ nghĩa).
--       * `conversation_sessions.scenario_id/persona_id`,
--         `movie_context_tts_fallback.persona_id`,
--         `movie_context_matches.tts_fallback_id/video_subtitle_index_id`
--         → cột nullable nhưng FK KHÔNG khai báo ON DELETE (mặc định NO ACTION,
--         chặn xoá bản ghi cha nếu còn tham chiếu) — lẽ ra theo nguyên tắc (d)
--         phải là SET NULL. Chưa gây sự cố vì thư viện `scenarios`/`personas`/
--         `movie_context_tts_fallback`/`video_subtitle_index` hiếm khi bị xoá
--         trong vòng đời demo, nhưng là hạn chế thật cần biết trước khi viết
--         logic xoá dữ liệu ở các bảng thư viện này.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS vector;        -- pgvector, dùng cho document_chunks.embedding[_local]


-- ============================================================================
-- CORE (tier: Đầy đủ / MVP)
-- ============================================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,                 -- bcrypt qua passlib
    display_name    VARCHAR(100),                          -- thêm ngoài thiết kế gốc
    native_language VARCHAR(10) DEFAULT 'vi',               -- thêm ngoài thiết kế gốc
    target_level    VARCHAR(10),                            -- nullable trong DB thật; thiết kế gốc: NOT NULL DEFAULT 'b1'
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()                -- có trigger trg_users_updated_at (xem TRIGGERS)
);

CREATE TABLE notebook_folders (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    folder_id       UUID REFERENCES notebook_folders(id) ON DELETE SET NULL,
    title           VARCHAR(255) NOT NULL,     -- thêm ngoài thiết kế gốc (hiển thị UI)
    source_type     VARCHAR(20) NOT NULL,
    source_url      TEXT,                       -- thêm ngoài thiết kế gốc
    file_path       TEXT,                       -- thêm ngoài thiết kế gốc (đường dẫn file gốc trên storage/)
    file_size_kb    INTEGER,
    tags            TEXT[],                     -- thiết kế gốc dùng JSONB '[]'
    starred         BOOLEAN DEFAULT false,
    language        VARCHAR(10) DEFAULT 'en',   -- thêm ngoài thiết kế gốc
    status          VARCHAR(20) DEFAULT 'processing',
    created_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_documents_source_type_valid CHECK (source_type IN ('audio', 'docx', 'doc', 'pdf')),
    CONSTRAINT chk_documents_status_valid CHECK (status IN ('processing', 'ready', 'failed'))
);

CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(768),               -- gemini-embedding-001 (EMBEDDING_PROVIDER=gemini)
    embedding_local vector(1024),              -- bge-m3 qua Ollama (EMBEDDING_PROVIDER=ollama, mặc định)
    page_or_line_ref VARCHAR(50),              -- thêm ngoài thiết kế gốc, hiện chưa thấy service nào set giá trị
    token_count     INTEGER,                    -- thêm ngoài thiết kế gốc
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- generated_passages.source_document_id: bổ sung cho Skim & Scan gắn tài liệu
-- thật (lumina_context.md mục 3.12) — thiết kế gốc của bảng này CHƯA từng có
-- cột này, đây là khác biệt thật quan trọng nhất của bảng, không phải cột phụ.
CREATE TABLE generated_passages (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic               VARCHAR(100),                       -- nullable trong DB thật; thiết kế gốc NOT NULL
    level               VARCHAR(10),                         -- nullable; thiết kế gốc NOT NULL cefr_level_enum
    title               VARCHAR(255),                        -- thêm ngoài thiết kế gốc
    content             TEXT NOT NULL,
    read_time_label     VARCHAR(20),                         -- thêm ngoài thiết kế gốc (UI)
    word_count_label    VARCHAR(20),                          -- thêm ngoài thiết kế gốc (UI)
    target_vocab_words  TEXT[],                               -- thêm ngoài thiết kế gốc
    source_document_id  UUID REFERENCES documents(id) ON DELETE SET NULL,   -- MỚI, xem ghi chú trên
    created_at          TIMESTAMPTZ DEFAULT now()
);


-- ============================================================================
-- MODULE 1 — READING & VOCAB (tier: Đầy đủ; Rearrange = Thử nghiệm giới hạn)
-- ============================================================================

CREATE TABLE reading_sessions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id             UUID REFERENCES documents(id) ON DELETE CASCADE,
    generated_passage_id    UUID REFERENCES generated_passages(id) ON DELETE CASCADE,
    mode                    VARCHAR(20) NOT NULL,
    score                   NUMERIC(5,2),
    time_taken_seconds      INTEGER,           -- thêm ngoài thiết kế gốc
    created_at              TIMESTAMPTZ DEFAULT now(),
    completed_at            TIMESTAMPTZ,
    CONSTRAINT chk_reading_source CHECK (
        (mode = 'classic'    AND document_id IS NOT NULL AND generated_passage_id IS NULL)
        OR
        (mode = 'skim_scan'  AND generated_passage_id IS NOT NULL AND document_id IS NULL)
    )
);

-- reading_answers.question/is_correct: có thật trong DB (câu hỏi lưu trực tiếp
-- ở đây, không chỉ ở nơi sinh đề) — thiết kế gốc thiếu 2 cột này.
-- source_chunk_id: chỉ set cho Classic Mode. Skim & Scan KHÔNG lưu trích dẫn
-- (passage_citation_ref đề xuất ở rà soát lần 3 chưa từng implement).
CREATE TABLE reading_answers (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reading_session_id          UUID NOT NULL REFERENCES reading_sessions(id) ON DELETE CASCADE,
    question                    TEXT NOT NULL,                   -- thêm ngoài thiết kế gốc
    options                      JSONB NOT NULL,
    correct_option_index        SMALLINT NOT NULL,
    selected_option_index        SMALLINT,
    is_correct                   BOOLEAN,                         -- thêm ngoài thiết kế gốc
    source_chunk_id              UUID REFERENCES document_chunks(id) ON DELETE SET NULL,
    created_at                   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE vocab_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id     UUID REFERENCES documents(id) ON DELETE SET NULL,
    term            VARCHAR(100) NOT NULL,
    ipa             VARCHAR(100),               -- thêm ngoài thiết kế gốc
    part_of_speech  VARCHAR(30),                -- thêm ngoài thiết kế gốc
    definition      TEXT,                        -- nullable trong DB thật; thiết kế gốc NOT NULL
    example_sentence TEXT,                        -- thêm ngoài thiết kế gốc
    synonyms        TEXT[],                        -- thiết kế gốc dùng JSONB
    antonyms        TEXT[],                         -- thiết kế gốc dùng JSONB
    source_url      TEXT,                            -- tier Thử nghiệm giới hạn (Browser Extension)
    created_at      TIMESTAMPTZ DEFAULT now(),
    -- "Đúng 1 nguồn khi tạo" validate ở API (schemas/vocab.py); CHECK ở DB chỉ
    -- cấm có CẢ HAI cùng lúc — document_id về NULL khi xoá tài liệu (SET NULL).
    CONSTRAINT chk_vocab_source_exactly_one CHECK (
        NOT (document_id IS NOT NULL AND source_url IS NOT NULL)
    )
);

-- vocab_reviews: KHÔNG có cột updated_at/trigger như thiết kế gốc giả định —
-- DB thật dùng last_grade + last_reviewed_at (ghi trực tiếp trong service SM-2
-- lúc review, không qua trigger).
CREATE TABLE vocab_reviews (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vocab_item_id   UUID NOT NULL UNIQUE REFERENCES vocab_items(id) ON DELETE CASCADE,
    ease_factor     NUMERIC(4,2) DEFAULT 2.5,
    interval_days   INTEGER DEFAULT 1,           -- thiết kế gốc DEFAULT 0
    repetitions     INTEGER DEFAULT 0,
    last_grade      SMALLINT,                    -- thêm ngoài thiết kế gốc (điểm SM-2 lượt gần nhất, 0-5)
    last_reviewed_at TIMESTAMPTZ,                 -- thêm ngoài thiết kế gốc
    next_review_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE contextual_guess_attempts (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vocab_item_id           UUID REFERENCES vocab_items(id) ON DELETE SET NULL,
    term                    VARCHAR(100) NOT NULL,        -- thiết kế gốc dùng TEXT
    challenge_sentence      TEXT NOT NULL,
    options                 JSONB NOT NULL,
    correct_option_index    SMALLINT NOT NULL,
    selected_option_index   SMALLINT,
    is_correct              BOOLEAN,                        -- thêm ngoài thiết kế gốc
    created_at              TIMESTAMPTZ DEFAULT now()
);

-- custom_stories: đơn giản hơn thiết kế gốc khá nhiều — KHÔNG có theme/length/
-- missing_terms (feature "chọn độ dài truyện" chưa implement, chỉ sinh 1 dạng
-- truyện duy nhất). vocab_item_ids là UUID[] thật (không phải JSONB).
CREATE TABLE custom_stories (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vocab_item_ids  UUID[] NOT NULL,               -- không enforce FK theo phần tử (xem GHI CHÚ CUỐI FILE)
    generated_text  TEXT NOT NULL,                  -- thiết kế gốc gọi là "content"
    created_at      TIMESTAMPTZ DEFAULT now()
);


-- ============================================================================
-- PERSONAS (dùng chung Podcast / Speaking / Movie Context) — tier: Đầy đủ
-- ============================================================================

CREATE TABLE personas (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(100) NOT NULL,
    provider    VARCHAR(30) NOT NULL,          -- thêm ngoài thiết kế gốc (vd 'elevenlabs')
    voice_id    VARCHAR(100) NOT NULL,          -- id giọng bên ElevenLabs
    accent_tag  VARCHAR(30),                    -- thêm ngoài thiết kế gốc
    description TEXT,                            -- thêm ngoài thiết kế gốc
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT now()
);


-- ============================================================================
-- MODULE 2 — LISTENING (tier: Đầy đủ)
-- ============================================================================

-- podcasts.script_text: kịch bản podcast do Gemini sinh trước khi TTS — thiết
-- kế gốc hoàn toàn không có cột này (chỉ có audio_url), đây là dữ liệu trung
-- gian bắt buộc phải lưu (không tái sinh lại được script khi cần transcript).
CREATE TABLE podcasts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    script_text         TEXT NOT NULL,                 -- MỚI so với thiết kế gốc, xem ghi chú trên
    audio_url           TEXT,                            -- nullable trong DB thật (rỗng khi status != ready)
    duration_seconds    INTEGER,                          -- thêm ngoài thiết kế gốc
    persona_id          UUID REFERENCES personas(id) ON DELETE SET NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'processing',
    created_at          TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_podcasts_status_valid CHECK (status IN ('processing', 'ready', 'failed'))
);

-- transcript_segments: cấu trúc THẬT khác hẳn thiết kế gốc — lưu Ở CẤP TỪNG
-- TỪ (word-level, phục vụ chấm Dictation theo từ), không phải theo câu/đoạn
-- (segment-level, text + start_ms/end_ms) như bản thiết kế ban đầu mô tả.
-- Đã ghi nhận sự khác biệt này từ lumina_context.md mục 3.13 nhưng chưa từng
-- sửa lại DDL ở file này cho tới lần đối chiếu này.
CREATE TABLE transcript_segments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    podcast_id      UUID NOT NULL REFERENCES podcasts(id) ON DELETE CASCADE,
    word_index      INTEGER NOT NULL,
    word_text       VARCHAR(100) NOT NULL,
    start_time_ms   INTEGER NOT NULL,
    end_time_ms     INTEGER NOT NULL
);

-- dictation_attempts: user_input_text/diff_result/accuracy_score thay cho
-- transcribed_text/score của thiết kế gốc; start_ms/end_ms thay bằng
-- start_word_index/end_word_index (đúng theo cấp từ của transcript_segments
-- ở trên, không phải mốc thời gian tuyệt đối).
CREATE TABLE dictation_attempts (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    podcast_id              UUID NOT NULL REFERENCES podcasts(id) ON DELETE CASCADE,
    user_input_text         TEXT NOT NULL,
    diff_result             JSONB,                          -- kết quả difflib chi tiết theo từ
    accuracy_score          NUMERIC(5,2),
    start_word_index        INTEGER,
    end_word_index          INTEGER,
    audio_segment_path      TEXT,
    reference_word_tags     JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{"word":"mitochondria","is_rare_or_proper":true}]
    created_at              TIMESTAMPTZ DEFAULT now()
);


-- ============================================================================
-- MODULE NOTEBOOK — RAG Chat (mới, mục 3.12 lumina_context.md — MỚI THÊM VÀO
-- FILE NÀY lần đối chiếu 2026-09-27; DB thật đã có bảng này từ lâu)
-- ============================================================================

CREATE TABLE notebook_chat_messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role            VARCHAR(10) NOT NULL,
    content         TEXT NOT NULL,
    sources         JSONB,                 -- mảng document_chunks.id trích dẫn cho câu trả lời 'assistant'
    created_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_notebook_chat_role_valid CHECK (role IN ('user', 'assistant'))
);


-- ============================================================================
-- MODULE 3 — WRITING (tier: Đầy đủ; Rearrange = Thử nghiệm giới hạn)
-- ============================================================================

-- writing_submissions: 2 CHECK ràng buộc "chấm xong phải có đủ điểm" mà bản
-- thiết kế gốc đề xuất (chk_writing_submissions_graded_complete,
-- chk_writing_submissions_rubric) CHƯA từng được áp vào DB thật — chỉ có 3
-- CHECK dưới đây tồn tại thật. Việc "chấm xong phải có rubric_scores/cefr/ielts"
-- hiện chỉ được đảm bảo ở tầng service (writing_service.py), không có lưới an
-- toàn ở DB.
CREATE TABLE writing_submissions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id         UUID REFERENCES documents(id) ON DELETE SET NULL,
    title               VARCHAR(255),                     -- thêm ngoài thiết kế gốc
    submitted_text      TEXT NOT NULL,
    overall_score       NUMERIC(5,2),                       -- thiết kế gốc gọi là "score"
    cefr_level          VARCHAR(15),                         -- thiết kế gốc dùng cefr_level_enum
    ielts_band          VARCHAR(15),                          -- thiết kế gốc dùng NUMERIC(2,1) — DB thật là chữ (vd "6.5")
    source_type         VARCHAR(20) NOT NULL DEFAULT 'document_summary',
    prompt_text         TEXT,
    certificate_style   VARCHAR(20),
    -- rubric_scores: {"task_response","coherence_cohesion","lexical_resource",
    -- "grammatical_range_accuracy"} thang 0-100, chỉ dùng cho extended_topic/
    -- free_topic — writing_service.submit_essay tự ghi user_errors
    -- (error_type='writing_coherence') khi coherence_cohesion thấp, KHÔNG qua
    -- trigger DB (đổi hướng so với đề xuất trigger ban đầu, xem TRIGGERS).
    rubric_scores       JSONB,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_writing_certificate_style_valid CHECK (
        certificate_style IS NULL OR certificate_style IN ('toeic', 'ielts', 'cambridge')
    ),
    CONSTRAINT chk_writing_document_id_by_source CHECK (
        source_type <> 'free_topic' OR document_id IS NULL
    ),
    CONSTRAINT chk_writing_source_type_valid CHECK (
        source_type IN ('document_summary', 'extended_topic', 'free_topic')
    )
);

-- writing_insights: title/description/rule/synonyms/suggestion thay cho
-- explanation đơn của thiết kế gốc — insight giờ có cấu trúc phong phú hơn
-- (tiêu đề + mô tả riêng, kèm rule tham chiếu và gợi ý synonym khi liên quan).
-- KHÔNG có CHECK ép offset chỉ tồn tại với insight_type='grammar' như thiết kế
-- gốc đề xuất — offset luôn nullable độc lập với insight_type trong DB thật.
CREATE TABLE writing_insights (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    writing_submission_id   UUID NOT NULL REFERENCES writing_submissions(id) ON DELETE CASCADE,
    insight_type            VARCHAR(20) NOT NULL,
    title                    VARCHAR(150) NOT NULL,        -- thêm ngoài thiết kế gốc
    description             TEXT NOT NULL,                  -- thiết kế gốc gọi là "explanation"
    original_text            TEXT,
    suggested_text            TEXT,
    error_start_offset        INTEGER,                       -- thiết kế gốc gọi là "offset_start"
    error_end_offset           INTEGER,                        -- thiết kế gốc gọi là "offset_end"
    rule                       TEXT,                            -- thêm ngoài thiết kế gốc
    synonyms                   JSONB,                            -- thêm ngoài thiết kế gốc
    suggestion                  TEXT,                             -- thêm ngoài thiết kế gốc
    created_at                  TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_writing_insights_type_valid CHECK (insight_type IN ('grammar', 'vocabulary', 'style'))
);

-- rephrase_requests: cấu trúc THẬT khác hẳn thiết kế gốc — mỗi GỢI Ý rephrase
-- là 1 DÒNG riêng (original_text/rephrased_text/style_target/explanation),
-- không phải 1 request chứa mảng JSONB suggested_sentences[] như thiết kế gốc.
-- routers/writing.py: rephrase() trả về nhiều dòng cho 1 câu gốc.
CREATE TABLE rephrase_requests (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    writing_submission_id   UUID REFERENCES writing_submissions(id) ON DELETE CASCADE,
    original_text            TEXT NOT NULL,               -- thiết kế gốc gọi là "original_sentence"
    rephrased_text            TEXT NOT NULL,                -- 1 gợi ý / dòng, không phải mảng
    style_target               VARCHAR(20),                   -- thêm ngoài thiết kế gốc
    explanation                 TEXT,
    created_at                   TIMESTAMPTZ DEFAULT now()
);


-- ============================================================================
-- MODULE 4 — SPEAKING (tier: Thử nghiệm giới hạn)
-- ============================================================================

CREATE TABLE scenarios (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title               VARCHAR(150) NOT NULL,           -- thêm ngoài thiết kế gốc
    description         TEXT,                              -- nullable trong DB thật; thiết kế gốc NOT NULL
    difficulty_level     VARCHAR(10),                        -- thêm ngoài thiết kế gốc
    target_intents        JSONB,                               -- thêm ngoài thiết kế gốc
    goal                   TEXT,                                 -- feature-speaking.md 3.3; nullable trong DB thật
    formality_level          VARCHAR(20) NOT NULL DEFAULT 'neutral'
);

-- conversation_sessions: mô hình vòng đời khác hẳn thiết kế gốc — DB thật theo
-- dõi status ('in_progress'/'completed'/'expired') + ended_at (1 phiên có
-- điểm kết thúc rõ ràng), thiết kế gốc chỉ có last_active_at (giả định phiên
-- không bao giờ "kết thúc" chính thức, chỉ có mốc hoạt động gần nhất).
-- scenario_id/persona_id đều nullable trong DB thật (thiết kế gốc: scenario_id
-- NOT NULL + ON DELETE RESTRICT).
CREATE TABLE conversation_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scenario_id     UUID REFERENCES scenarios(id),         -- không có ON DELETE, xem LƯU Ý đầu file
    persona_id      UUID REFERENCES personas(id),           -- không có ON DELETE, xem LƯU Ý đầu file
    status          VARCHAR(20) DEFAULT 'in_progress',
    started_at      TIMESTAMPTZ DEFAULT now(),
    ended_at        TIMESTAMPTZ,                              -- thiết kế gốc gọi là "last_active_at", ý nghĩa khác
    CONSTRAINT chk_conversation_sessions_status_valid CHECK (status IN ('in_progress', 'completed', 'expired'))
);

-- conversation_turns: cấu trúc THẬT khác hẳn thiết kế gốc (đổi tên gần như mọi
-- cột) — transcription/response_text (thiết kế gốc) → user_transcript/
-- ai_response_text; thêm corrected_transcript, was_error_detected,
-- pronunciation_advice, cefr_tip, grammar_tip, ai_response_audio_url,
-- turn_index (thứ tự lượt nói trong phiên). pronunciation_score/intent_score/
-- politeness_score là NUMERIC(5,2) (thiết kế gốc: INTEGER 0-100 CHECK) — DB
-- thật không có CHECK giới hạn khoảng giá trị 0-100 cho 3 cột điểm này.
CREATE TABLE conversation_turns (
    id                                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_session_id             UUID NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    turn_index                          INTEGER NOT NULL,
    user_audio_url                      TEXT,
    user_transcript                     TEXT,
    corrected_transcript                 TEXT,                -- thêm ngoài thiết kế gốc
    was_error_detected                    BOOLEAN DEFAULT false, -- thêm ngoài thiết kế gốc
    pronunciation_score                    NUMERIC(5,2),
    pronunciation_advice                     TEXT,               -- thêm ngoài thiết kế gốc
    pronunciation_assessment_failed            BOOLEAN NOT NULL DEFAULT false,
    intent_score                                 NUMERIC(5,2),      -- đề xuất, chưa chốt rubric (mục 4 điểm 6)
    intent_feedback                               TEXT,
    politeness_score                                NUMERIC(5,2),   -- đề xuất, chưa chốt rubric (mục 4 điểm 6)
    politeness_feedback                              TEXT,
    cefr_tip                                          JSONB,          -- thêm ngoài thiết kế gốc
    grammar_tip                                         TEXT,          -- thêm ngoài thiết kế gốc
    ai_response_text                                     TEXT,          -- thiết kế gốc gọi là "response_text"
    ai_response_audio_url                                 TEXT,          -- thêm ngoài thiết kế gốc
    stt_provider_used                                       VARCHAR(20),
    suggested_phrases                                         JSONB,
    natural_rephrase                                          TEXT,          -- migration 20261001_0020
    literal_translation                                       JSONB,         -- [{original, natural, explanation}]; thêm ở migration 20261001_0020 tên "vietnglish", đổi tên ở 20261001_0021
    created_at                                                 TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE slang_phrases (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phrase_text         VARCHAR(150) NOT NULL,
    meaning              TEXT NOT NULL,
    example_sentence      TEXT,                          -- nullable trong DB thật; thiết kế gốc NOT NULL
    formality_level        VARCHAR(20) NOT NULL DEFAULT 'neutral',
    topic_tags              VARCHAR[],                     -- thiết kế gốc dùng JSONB
    source_reference          VARCHAR(150) NOT NULL,        -- tên nguồn, phục vụ trích dẫn học thuật
    CONSTRAINT ck_slang_source_not_empty CHECK (source_reference <> '')
);

-- user_phrasebook_entries: phrase_text NOT NULL trong DB thật (luôn snapshot
-- nội dung tại thời điểm lưu, dù có slang_phrase_id hay không) — khác thiết kế
-- gốc (nullable, chỉ bắt buộc khi slang_phrase_id NULL qua CHECK
-- chk_phrasebook_has_content, CHECK này KHÔNG tồn tại trong DB thật).
CREATE TABLE user_phrasebook_entries (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slang_phrase_id             UUID REFERENCES slang_phrases(id) ON DELETE SET NULL,
    conversation_turn_id        UUID REFERENCES conversation_turns(id) ON DELETE SET NULL,
    phrase_text                 VARCHAR(150) NOT NULL,
    meaning                      TEXT,
    example_sentence              TEXT,
    formality_level                 VARCHAR(20),           -- thêm ngoài thiết kế gốc
    created_at                       TIMESTAMPTZ DEFAULT now()
);

-- realtime_conversation_metrics: định hướng mở rộng, THEO PHIÊN (conversation_
-- session_id) trong DB thật — không phải theo từng lượt nói (conversation_
-- turn_id) như thiết kế gốc. Cột avg_latency_ms/interruption_count/
-- stream_status đã có sẵn (rỗng) từ trước, chờ nâng cấp streaming thật.
CREATE TABLE realtime_conversation_metrics (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_session_id     UUID NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    avg_latency_ms               INTEGER,
    interruption_count             INTEGER DEFAULT 0,
    stream_status                   VARCHAR(20)
);


-- ============================================================================
-- MODULE 0 — ADAPTIVE LEARNING ENGINE (tier: Đầy đủ)
-- ============================================================================

CREATE TABLE quizzes (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generated_from_error_ids     UUID[],           -- không có FK theo phần tử (mảng)
    focus_error_types             JSONB,
    questions                       JSONB NOT NULL,
    created_at                       TIMESTAMPTZ DEFAULT now()
);

-- quiz_attempts: cột thật là attempt_type (nullable — NULL = lượt làm đề động
-- Adaptive Engine, không có giá trị 'adaptive_dynamic' minh bạch như thiết kế
-- gốc đề xuất; CHECK chỉ chấp nhận 'rearrange_reading'/'rearrange_writing' khi
-- KHÁC NULL). quiz_id → quizzes ON DELETE CASCADE (khác nguyên tắc SET NULL đã
-- công bố, xem LƯU Ý đầu file). completed_at DEFAULT now() thực chất được set
-- ngay lúc INSERT (đóng vai trò như created_at, không phải mốc "chấm xong").
-- KHÔNG có CHECK chk_quiz_attempts_open_form như thiết kế gốc đề xuất.
CREATE TABLE quiz_attempts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quiz_id         UUID REFERENCES quizzes(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    attempt_type    VARCHAR(30),                 -- thiết kế gốc gọi là "quiz_type", KHÔNG NULL
    is_open_form    BOOLEAN,
    answers         JSONB,
    payload         JSONB,                         -- thêm ngoài thiết kế gốc
    score           NUMERIC(5,2),
    completed_at    TIMESTAMPTZ DEFAULT now(),       -- xem ghi chú trên — thực chất là "created_at"
    CONSTRAINT chk_quiz_attempts_attempt_type_valid CHECK (
        attempt_type IS NULL OR attempt_type IN ('rearrange_reading', 'rearrange_writing')
    )
);

-- user_errors.error_type: CHECK trong DB thật ĐÃ CHỐT đúng 9 giá trị đề xuất ở
-- api-spec.md mục 9 — về mặt vận hành coi như đã "chốt chính thức" (chạy thật
-- trong production DB), nhưng lumina_context.md mục 4 điểm 1 vẫn liệt kê là
-- "cần xác nhận lại" ở tầng tài liệu/học thuật — 2 việc khác nhau, giữ nguyên
-- cả hai ghi chú cho tới khi người dùng xác nhận chính thức bằng văn bản.
CREATE TABLE user_errors (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quiz_attempt_id             UUID REFERENCES quiz_attempts(id) ON DELETE SET NULL,
    error_type                  VARCHAR(30) NOT NULL,
    spaced_repetition_level     INTEGER NOT NULL DEFAULT 0,
    detail                      JSONB,          -- { source, original_text?, corrected_text?, explanation? }
    created_at                  TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_user_errors_error_type_valid CHECK (error_type IN (
        'grammar', 'vocabulary', 'spelling', 'pronunciation', 'listening_comprehension',
        'reading_comprehension', 'writing_coherence', 'communicative_intent', 'politeness'
    ))
);

-- review_priority_queue: item_type/item_id/last_calculated_at thay cho
-- source_type/source_id/created_at của thiết kế gốc — cùng bản chất tham
-- chiếu đa hình (KHÔNG có FK cứng, xem GHI CHÚ CUỐI FILE), backend tính lại
-- toàn bộ hàng đợi mỗi lần đọc (priority_queue_service.py), không phải bảng
-- lưu trữ lâu dài.
CREATE TABLE review_priority_queue (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_type       VARCHAR(20) NOT NULL,
    item_id         UUID NOT NULL,
    priority_score  NUMERIC(6,2) NOT NULL,
    last_calculated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_review_priority_item_type_valid CHECK (item_type IN ('vocab', 'error'))
);

-- streaks: user_id CHÍNH LÀ khóa chính (không có cột id riêng như thiết kế
-- gốc) — quan hệ 1-1 với users được enforce trực tiếp bằng PK, không cần UNIQUE.
CREATE TABLE streaks (
    user_id             UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    current_streak      INTEGER DEFAULT 0,
    longest_streak       INTEGER DEFAULT 0,
    last_active_date      DATE,
    total_xp                INTEGER DEFAULT 0,       -- XP tích luỹ (Gamification, migration 20260920_0012)
    lost_streak             INTEGER NOT NULL DEFAULT 0,  -- chuỗi vừa đứt, khôi phục bằng quiz (migration 20261001_0020)
    lost_on                 DATE,
    freezes_available       INTEGER NOT NULL DEFAULT 0   -- freeze tặng mỗi 7 ngày liên tiếp, tối đa 2 (migration 20261001_0020)
);

CREATE TABLE skill_progress (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_name  VARCHAR(30) NOT NULL,          -- thiết kế gốc dùng skill_enum
    cefr_level  VARCHAR(20),                    -- chỉ writing có giá trị (LLM ước lượng)
    score       NUMERIC(5,2),                    -- trung bình động 0-100 (gamification_service.record_skill_score)
    updated_at  TIMESTAMPTZ DEFAULT now(),          -- có trigger trg_skill_progress_updated_at
    UNIQUE (user_id, skill_name),
    CONSTRAINT chk_skill_progress_skill_valid CHECK (skill_name IN ('reading', 'listening', 'writing', 'speaking'))
);


-- ============================================================================
-- AUTH / BROWSER EXTENSION (tier: Đầy đủ + Thử nghiệm giới hạn)
-- ============================================================================

CREATE TABLE refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL UNIQUE,     -- thiết kế gốc dùng TEXT
    is_revoked      BOOLEAN DEFAULT false,              -- thiết kế gốc gọi là "revoked"
    -- Phạm vi token Extension (điểm mở #13, đã chốt): client_type='extension'
    -- CHỈ được phép gọi /api/extension/* + /api/reading/lookup + /api/vocab.
    -- Chính sách TĨNH, enforce ở middleware (app/core/extension_scope.py),
    -- không phải ở DB.
    client_type     VARCHAR(20) NOT NULL DEFAULT 'web',
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_refresh_tokens_client_type CHECK (client_type IN ('web', 'extension'))
);


-- ============================================================================
-- MODULE 5 — MOVIE DELIVERY CONTEXT (tier: Thử nghiệm giới hạn + Định hướng mở rộng)
-- ============================================================================

-- movie_context_tts_fallback: persona_id NULLABLE trong DB thật (thiết kế gốc:
-- NOT NULL + ON DELETE RESTRICT) — cache dùng chung (câu, persona), tra bằng
-- IS NOT DISTINCT FROM vì UNIQUE constraint thường không chặn được persona
-- NULL trùng nhau.
CREATE TABLE movie_context_tts_fallback (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phrase_text     TEXT NOT NULL,
    persona_id      UUID REFERENCES personas(id),   -- không có ON DELETE, xem LƯU Ý đầu file
    audio_url       TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- video_sources/video_subtitle_index: nhánh "tìm phụ đề trong kho video demo"
-- (lumina_context.md mục 3.14, 2026-09-26/27) — không còn thuần là "Định
-- hướng mở rộng chưa build" như thiết kế gốc giả định, đã có dữ liệu thật
-- (3 cảnh mô phỏng + 2 phim thật public domain/CC BY, tổng ~330 câu đã đánh
-- chỉ mục). Đổi tên cột: url→video_url, phrase→phrase_text, timestamp_ms
-- (1 điểm mốc) → start_time_ms/end_time_ms (khoảng thời gian, đúng với việc
-- cần nhảy tới TRƯỚC dòng khớp 2,5 giây và tô màu đúng khoảng phụ đề).
CREATE TABLE video_sources (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title               VARCHAR(255),
    platform            VARCHAR(30),                    -- thêm ngoài thiết kế gốc (vd 'film', 'demo')
    video_url           TEXT NOT NULL,
    subtitle_language   VARCHAR(10) DEFAULT 'en'
);

CREATE TABLE video_subtitle_index (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_source_id     UUID NOT NULL REFERENCES video_sources(id) ON DELETE CASCADE,
    phrase_text         TEXT NOT NULL,
    start_time_ms        INTEGER NOT NULL,
    end_time_ms            INTEGER NOT NULL
);

-- movie_context_matches: có thêm user_id trong DB thật — mỗi lượt tìm kiếm
-- được gắn với user (lịch sử tìm kiếm cá nhân), thiết kế gốc coi bảng này là
-- kết quả match dùng chung, không gắn user. Nguồn cache dùng chung thật sự chỉ
-- còn ở movie_context_tts_fallback/video_subtitle_index (2 bảng phía trên).
-- search_phrase thay cho "phrase" của thiết kế gốc.
CREATE TABLE movie_context_matches (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    search_phrase                VARCHAR(255) NOT NULL,
    source_type                    VARCHAR(20) NOT NULL,
    video_subtitle_index_id          UUID REFERENCES video_subtitle_index(id),  -- không có ON DELETE, xem LƯU Ý đầu file
    tts_fallback_id                    UUID REFERENCES movie_context_tts_fallback(id),  -- không có ON DELETE, xem LƯU Ý đầu file
    is_saved                             BOOLEAN DEFAULT false,
    created_at                             TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_exactly_one_source CHECK (
        (source_type = 'real_video'   AND video_subtitle_index_id IS NOT NULL AND tts_fallback_id IS NULL)
        OR
        (source_type = 'tts_fallback' AND tts_fallback_id IS NOT NULL AND video_subtitle_index_id IS NULL)
    )
);


-- ============================================================================
-- INDEXES (tên index đúng như trong DB thật — khác quy ước idx_<table>_<col>
-- đầy đủ mà thiết kế gốc dùng; nhiều index rút gọn tên bảng, vd idx_chunks_*
-- cho document_chunks, idx_turns_* cho conversation_turns)
-- ============================================================================

CREATE INDEX idx_notebook_folders_user ON notebook_folders(user_id);
CREATE INDEX idx_documents_user ON documents(user_id);
CREATE INDEX idx_documents_folder ON documents(folder_id);
CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_chunks_embedding_local_hnsw ON document_chunks USING hnsw (embedding_local vector_cosine_ops);
CREATE INDEX idx_generated_passages_user ON generated_passages(user_id);
CREATE INDEX idx_generated_passages_source_document ON generated_passages(source_document_id);

CREATE INDEX idx_reading_sessions_user ON reading_sessions(user_id);
CREATE INDEX idx_reading_sessions_document ON reading_sessions(document_id);
CREATE INDEX idx_reading_sessions_passage ON reading_sessions(generated_passage_id);
CREATE INDEX idx_reading_answers_session ON reading_answers(reading_session_id);
CREATE INDEX idx_reading_answers_source_chunk ON reading_answers(source_chunk_id);

CREATE UNIQUE INDEX uq_vocab_items_user_term ON vocab_items(user_id, lower(term));  -- API trả 409 khi trùng
CREATE INDEX idx_vocab_user ON vocab_items(user_id);
CREATE INDEX idx_vocab_document ON vocab_items(document_id);
CREATE INDEX idx_vocab_reviews_next ON vocab_reviews(next_review_at);
CREATE INDEX idx_contextual_guess_user ON contextual_guess_attempts(user_id);
CREATE INDEX idx_contextual_guess_vocab_item ON contextual_guess_attempts(vocab_item_id);
CREATE INDEX idx_custom_stories_user ON custom_stories(user_id);

CREATE INDEX idx_podcasts_document ON podcasts(document_id);
CREATE INDEX idx_transcript_podcast ON transcript_segments(podcast_id);
CREATE UNIQUE INDEX uq_transcript_segments_podcast_word ON transcript_segments(podcast_id, word_index);
CREATE INDEX idx_dictation_attempts_podcast ON dictation_attempts(podcast_id);
CREATE INDEX idx_dictation_attempts_user ON dictation_attempts(user_id);

CREATE INDEX idx_notebook_chat_messages_document ON notebook_chat_messages(document_id, created_at);

CREATE INDEX idx_writing_submissions_user ON writing_submissions(user_id);
CREATE INDEX idx_writing_submissions_document ON writing_submissions(document_id);
CREATE INDEX idx_writing_insights_submission ON writing_insights(writing_submission_id);
CREATE INDEX idx_rephrase_requests_submission ON rephrase_requests(writing_submission_id);

CREATE INDEX idx_conversation_sessions_user ON conversation_sessions(user_id);
CREATE INDEX idx_turns_session ON conversation_turns(conversation_session_id);
CREATE UNIQUE INDEX uq_conversation_turns_session_turn ON conversation_turns(conversation_session_id, turn_index);
-- (3 unique index dưới cùng nhóm: tạo bằng CREATE UNIQUE INDEX riêng trong DB
-- thật, không phải UNIQUE inline trong CREATE TABLE — giữ đúng cách này để tên
-- index khớp 100% với DB thật khi đối chiếu bằng psql \d.)
CREATE INDEX idx_phrasebook_user ON user_phrasebook_entries(user_id);
CREATE INDEX idx_phrasebook_slang_phrase ON user_phrasebook_entries(slang_phrase_id);
CREATE INDEX idx_phrasebook_conversation_turn ON user_phrasebook_entries(conversation_turn_id);

CREATE INDEX idx_quizzes_user ON quizzes(user_id);
CREATE INDEX idx_quiz_attempts_user ON quiz_attempts(user_id);
CREATE INDEX idx_quiz_attempts_quiz ON quiz_attempts(quiz_id);
CREATE INDEX idx_user_errors_user_id_error_type ON user_errors(user_id, error_type);
CREATE INDEX idx_user_errors_quiz_attempt ON user_errors(quiz_attempt_id);
CREATE INDEX idx_priority_user ON review_priority_queue(user_id, priority_score DESC);

CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);

CREATE UNIQUE INDEX uq_tts_fallback_phrase_persona ON movie_context_tts_fallback(phrase_text, persona_id);
CREATE INDEX idx_movie_matches_user ON movie_context_matches(user_id, is_saved);
-- ĐÃ XÁC MINH (2026-09-27, đọc trực tiếp movie_context_service.py): index này
-- dùng cấu hình 'english' nhưng service._search_real_video() query bằng
-- to_tsvector('simple', ...) (đổi qua 'simple' để không mất idiom nhiều
-- stopword như "hang out"/"you can say that again" — 'english' bỏ mất các từ
-- đó). Biểu thức không khớp nên Postgres KHÔNG tận dụng được index GIN này,
-- luôn quét tuần tự — đây là đánh đổi CÓ CHỦ ĐÍCH, tác giả đã tự ghi chú
-- (`ponytail:`) là chấp nhận được ở quy mô vài chục dòng phụ đề hiện tại,
-- hướng nâng cấp đã ghi sẵn: thêm 1 index GIN theo 'simple' khi kho video lớn
-- lên. Giữ index 'english' này lại làm tài liệu lịch sử (không xoá), không
-- phải lỗi cần sửa.
CREATE INDEX idx_subtitle_phrase ON video_subtitle_index USING gin (to_tsvector('english', phrase_text));


-- ============================================================================
-- TRIGGERS (DB thật CHỈ có 2 trigger — KHÔNG có trg_vocab_reviews_updated_at
-- (vocab_reviews không có cột updated_at, xem bảng ở trên) và KHÔNG có trigger
-- ghi user_errors('writing_coherence') như đề xuất ban đầu — logic đó đã
-- chuyển hẳn vào writing_service.submit_essay, xem ghi chú tại writing_submissions.)
-- ============================================================================

CREATE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_skill_progress_updated_at
    BEFORE UPDATE ON skill_progress
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();


-- ============================================================================
-- GHI CHÚ CUỐI FILE
-- ============================================================================
-- 1. custom_stories.vocab_item_ids và quizzes.focus_error_types/
--    generated_from_error_ids là mảng (UUID[]/JSONB), KHÔNG enforce FK theo
--    từng phần tử — giới hạn đã biết của thiết kế gốc, chấp nhận được ở quy mô
--    khóa luận. Nếu cần toàn vẹn tham chiếu chặt hơn, chuyển thành bảng nối
--    (junction table) — ngoài phạm vi rà soát lần này.
-- 2. review_priority_queue.item_id là tham chiếu đa hình (vocab_reviews.id
--    hoặc user_errors.id tùy item_type), không có FK cứng — bảng này thực ra
--    KHÔNG lưu trữ lâu dài, priority_queue_service.py tính lại toàn bộ mỗi lần
--    đọc; xem ghi chú tại chỗ định nghĩa bảng.
-- 3. error_type: CHECK trong DB thật đã chốt đúng 9 giá trị đề xuất — coi như
--    "chốt vận hành", nhưng lumina_context.md mục 4 điểm 1 vẫn cần 1 xác nhận
--    chính thức bằng văn bản (khóa luận) trước khi coi là chốt hoàn toàn.
--    quiz_attempts.attempt_type (2 giá trị, không có 'adaptive_dynamic' minh
--    bạch — NULL đóng vai trò ngầm định cho Adaptive Engine) vẫn ở trạng thái
--    "đề xuất trong thiết kế gốc, chưa từng thêm giá trị thứ 3 vào CHECK thật".
-- 4. Native Postgres ENUM (CREATE TYPE ... AS ENUM) KHÔNG được dùng ở đâu
--    trong DB thật — mọi cột "enum" đều là VARCHAR(n) + CHECK. Quyết định này
--    chưa từng được ghi nhận rõ ràng ở nơi nào khác trước bản đối chiếu này;
--    nên coi là quyết định kiến trúc đã-thành-thực-tế (de facto), tương tự
--    trường hợp gọi thẳng google-generativeai thay vì qua LangChain.
-- ============================================================================
