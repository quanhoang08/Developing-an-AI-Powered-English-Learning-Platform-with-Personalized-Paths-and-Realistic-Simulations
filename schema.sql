-- ============================================================
-- SCHEMA: AI-Powered English Learning Platform
-- PostgreSQL 15+ với pgvector extension
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- BỔ SUNG: hàm dùng chung để trigger tự cập nhật updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- NHÓM LÕI: USERS
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(100),
    native_language VARCHAR(10) DEFAULT 'vi',
    target_level    VARCHAR(10),          -- CEFR: A1..C2
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- BỔ SUNG: trigger tự cập nhật updated_at mỗi lần UPDATE users
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- BỔ SUNG: refresh_tokens — cho phép thu hồi (revoke) khi logout / phát hiện lộ token.
-- JWT access token thuần không tự thu hồi được, nên cần bảng này để auth_service
-- kiểm tra token còn hiệu lực hay đã bị revoke trước khi cấp access token mới.
CREATE TABLE refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL UNIQUE,  -- lưu hash, không lưu token thô
    is_revoked      BOOLEAN DEFAULT false,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);

-- ============================================================
-- NHÓM LÕI: DOCUMENTS + RAG (Notebook Base)
-- ============================================================

CREATE TABLE notebook_folders (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,     -- 'IELTS Vocabulary Lists', 'Grammar Workbooks'...
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- BỔ SUNG
CREATE INDEX idx_notebook_folders_user ON notebook_folders(user_id);

CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    folder_id       UUID REFERENCES notebook_folders(id) ON DELETE SET NULL,
    title           VARCHAR(255) NOT NULL,
    source_type     VARCHAR(20) NOT NULL,  -- 'pdf' | 'txt' | 'docx' | 'link' | 'youtube'
    source_url      TEXT,
    file_path       TEXT,
    file_size_kb    INT,
    tags            TEXT[],                -- ['IELTS', 'B2 Upper', 'Tech']
    starred         BOOLEAN DEFAULT false,
    language        VARCHAR(10) DEFAULT 'en',
    status          VARCHAR(20) DEFAULT 'processing', -- processing | ready | failed
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_documents_user ON documents(user_id);
CREATE INDEX idx_documents_folder ON documents(folder_id);

-- SỬA: vector(768) thay vì vector(1536) — 768 khớp đúng chiều embedding của
-- Gemini "models/text-embedding-004" (GEMINI_EMBEDDING_MODEL trong config.py).
-- LƯU Ý QUAN TRỌNG: nếu sau này đổi model embedding trong config.py sang model
-- khác chiều (vd OpenAI text-embedding-3-small = 1536), PHẢI đổi lại số này
-- và tạo migration mới — 2 nơi phải luôn khớp nhau, không tự động đồng bộ.
CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(768),           -- SỬA: khớp Gemini text-embedding-004 (768 chiều)
    page_or_line_ref VARCHAR(50),          -- dùng cho trích dẫn nguồn (Classic Mode)
    token_count     INT,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_chunks_document ON document_chunks(document_id);
-- SỬA: thêm WITH (lists = 100) — mặc định lists=1 khiến ivfflat gần như vô dụng
-- khi dữ liệu lớn dần; 100 là mốc hợp lý cho quy mô vài chục nghìn chunk (khoá luận).
CREATE INDEX idx_chunks_embedding ON document_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- MỨC 1 — ĐỌC & TỪ VỰNG
-- ============================================================

CREATE TABLE vocab_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id     UUID REFERENCES documents(id) ON DELETE SET NULL,
    term            VARCHAR(100) NOT NULL,
    ipa             VARCHAR(100),
    part_of_speech  VARCHAR(30),
    definition      TEXT,
    example_sentence TEXT,
    synonyms        TEXT[],
    antonyms        TEXT[],
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_vocab_user ON vocab_items(user_id);

-- Spaced Repetition (thuật toán SM-2)
CREATE TABLE vocab_reviews (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vocab_item_id   UUID NOT NULL UNIQUE REFERENCES vocab_items(id) ON DELETE CASCADE,
    ease_factor     NUMERIC(4,2) DEFAULT 2.5,
    interval_days   INT DEFAULT 1,
    repetitions     INT DEFAULT 0,
    last_grade      SMALLINT,              -- 0-5 theo thang SM-2
    last_reviewed_at TIMESTAMPTZ,
    next_review_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_vocab_reviews_next ON vocab_reviews(next_review_at);

-- Đoạn văn do AI tự sinh cho Skim & Scan (theo topic/level, KHÔNG bắt nguồn từ tài liệu Notebook —
-- phát hiện từ server.ts /api/ai/generate-story: sinh mới mỗi lần, độc lập với documents)
CREATE TABLE generated_passages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic           VARCHAR(100),
    level           VARCHAR(10),           -- CEFR: A1..C2
    title           VARCHAR(255),
    content         TEXT NOT NULL,
    read_time_label VARCHAR(20),           -- '8 min read'
    word_count_label VARCHAR(20),          -- '1,200 words'
    target_vocab_words TEXT[],
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- BỔ SUNG
CREATE INDEX idx_generated_passages_user ON generated_passages(user_id);

-- Skim & Scan dùng generated_passages; Classic Mode dùng documents (tài liệu thật của người dùng)
CREATE TABLE reading_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    generated_passage_id UUID REFERENCES generated_passages(id) ON DELETE CASCADE,
    mode            VARCHAR(20) NOT NULL,  -- 'skim_scan' | 'classic'
    score           NUMERIC(5,2),
    time_taken_seconds INT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_reading_source CHECK (
        (mode = 'classic' AND document_id IS NOT NULL AND generated_passage_id IS NULL)
        OR
        (mode = 'skim_scan' AND generated_passage_id IS NOT NULL AND document_id IS NULL)
    )
);
-- BỔ SUNG
CREATE INDEX idx_reading_sessions_user ON reading_sessions(user_id);

CREATE TABLE reading_answers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reading_session_id UUID NOT NULL REFERENCES reading_sessions(id) ON DELETE CASCADE,
    question        TEXT NOT NULL,
    options         JSONB NOT NULL,        -- ["Decreased efficiency", "Loss of problem-solving skills", ...]
    correct_option_index SMALLINT NOT NULL,
    selected_option_index SMALLINT,
    is_correct      BOOLEAN,
    source_chunk_id UUID REFERENCES document_chunks(id),  -- trích dẫn nguồn (Classic Mode)
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- BỔ SUNG
CREATE INDEX idx_reading_answers_session ON reading_answers(reading_session_id);

-- Contextual Guessing (thực chất là bài tập điền khuyết trắc nghiệm — challengeSentence/challengeOptions).
-- vocab_item_id để NULL được vì thử thách này áp dụng ngay khi tra một từ bất kỳ,
-- kể cả khi người dùng CHƯA lưu từ đó vào sổ từ vựng (chỉ lưu khi bấm "save").
CREATE TABLE contextual_guess_attempts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vocab_item_id   UUID REFERENCES vocab_items(id) ON DELETE SET NULL,
    term            VARCHAR(100) NOT NULL, -- lưu trực tiếp từ, không phụ thuộc từ đã được lưu hay chưa
    challenge_sentence TEXT NOT NULL,      -- câu điền khuyết do AI sinh, khác example_sentence gốc
    options         JSONB NOT NULL,
    correct_option_index SMALLINT NOT NULL,
    selected_option_index SMALLINT,
    is_correct      BOOLEAN,
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- BỔ SUNG
CREATE INDEX idx_contextual_guess_user ON contextual_guess_attempts(user_id);

-- AI Custom Story
CREATE TABLE custom_stories (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vocab_item_ids  UUID[] NOT NULL,       -- các từ được yêu cầu đưa vào truyện
    generated_text  TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- BỔ SUNG
CREATE INDEX idx_custom_stories_user ON custom_stories(user_id);

-- ============================================================
-- MỨC 1 — NGHE
-- ============================================================

CREATE TABLE podcasts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    script_text     TEXT NOT NULL,
    audio_url       TEXT,
    duration_seconds INT,
    persona_ids     UUID[],                -- tham chiếu personas.id (giọng dùng trong podcast)
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE transcript_segments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    podcast_id      UUID NOT NULL REFERENCES podcasts(id) ON DELETE CASCADE,
    word_index      INT NOT NULL,
    word_text       VARCHAR(100) NOT NULL,
    start_time_ms   INT NOT NULL,
    end_time_ms     INT NOT NULL
);
CREATE INDEX idx_transcript_podcast ON transcript_segments(podcast_id);

CREATE TABLE dictation_attempts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    podcast_id      UUID REFERENCES podcasts(id) ON DELETE SET NULL,
    user_input_text TEXT NOT NULL,
    diff_result     JSONB,                 -- kết quả so khớp chi tiết (vị trí lỗi gõ)
    accuracy_score  NUMERIC(5,2),
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- BỔ SUNG
CREATE INDEX idx_dictation_attempts_user ON dictation_attempts(user_id);

-- ============================================================
-- MỨC 1 — VIẾT
-- ============================================================

CREATE TABLE writing_submissions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id     UUID REFERENCES documents(id) ON DELETE SET NULL,
    prompt_type     VARCHAR(20) NOT NULL,  -- 'summary' | 'free_writing'
    title           VARCHAR(255),
    submitted_text  TEXT NOT NULL,
    overall_score   NUMERIC(5,2),
    cefr_level      VARCHAR(15),           -- 'B2 Upper', 'C1'...
    ielts_band      VARCHAR(15),           -- '6.5 IELTS'
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- BỔ SUNG
CREATE INDEX idx_writing_submissions_user ON writing_submissions(user_id);

-- Thay grammar_corrections (offset-only) bằng bảng đa hình writing_insights,
-- vì AI thực tế trả về 3 loại insight có cấu trúc khác nhau: grammar (có offset),
-- vocabulary (gợi ý từ đồng nghĩa), style (gợi ý viết lại cả câu/đoạn).
CREATE TABLE writing_insights (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    writing_submission_id UUID NOT NULL REFERENCES writing_submissions(id) ON DELETE CASCADE,
    insight_type    VARCHAR(20) NOT NULL,  -- 'grammar' | 'vocabulary' | 'style'
    title           VARCHAR(150) NOT NULL,
    description     TEXT NOT NULL,
    original_text   TEXT,                  -- dùng cho grammar/vocabulary
    suggested_text  TEXT,                  -- dùng cho grammar
    error_start_offset INT,                -- chỉ áp dụng cho grammar (vị trí trong submitted_text)
    error_end_offset   INT,
    rule            TEXT,                  -- giải thích quy tắc, dùng cho grammar
    synonyms        JSONB,                 -- dùng cho vocabulary
    suggestion      TEXT,                  -- đoạn viết lại đề xuất, dùng cho style
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- BỔ SUNG
CREATE INDEX idx_writing_insights_submission ON writing_insights(writing_submission_id);

CREATE TABLE rephrase_requests (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    writing_submission_id UUID REFERENCES writing_submissions(id) ON DELETE CASCADE,
    original_text   TEXT NOT NULL,
    rephrased_text  TEXT NOT NULL,
    style_target    VARCHAR(20),           -- CEFR band / IELTS band mục tiêu
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- BỔ SUNG
CREATE INDEX idx_rephrase_requests_submission ON rephrase_requests(writing_submission_id);

-- ============================================================
-- NHÓM LÕI: GIỌNG NÓI (không clone người thật)
-- ============================================================

CREATE TABLE personas (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100) NOT NULL,     -- tên nhân vật gốc do nhóm đặt
    provider        VARCHAR(30) NOT NULL,      -- 'elevenlabs' | 'azure'
    voice_id        VARCHAR(100) NOT NULL,     -- id giọng trong thư viện đã cấp phép
    accent_tag      VARCHAR(30),               -- 'us_southern' | 'uk_cockney' | null
    description     TEXT
);

CREATE TABLE accents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(50) NOT NULL,      -- 'Southern US' | 'British Cockney'
    persona_id      UUID NOT NULL REFERENCES personas(id),
    slang_terms     JSONB,                     -- danh sách từ lóng đặc trưng để tiêm vào prompt
    status          VARCHAR(20) DEFAULT 'active' -- active | planned (Mức 3 mở rộng)
);

-- ============================================================
-- MỨC 2 — NÓI: AI Conversation Partner (turn-based)
-- ============================================================

CREATE TABLE scenarios (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title           VARCHAR(150) NOT NULL,
    description     TEXT,
    difficulty_level VARCHAR(10),           -- A1..C2
    target_intents  JSONB                   -- các ý định giao tiếp cần đạt (vd: "đặt bàn nhà hàng lịch sự")
);

CREATE TABLE conversation_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scenario_id     UUID REFERENCES scenarios(id),
    persona_id      UUID REFERENCES personas(id),
    status          VARCHAR(20) DEFAULT 'in_progress', -- in_progress | completed
    started_at      TIMESTAMPTZ DEFAULT now(),
    ended_at        TIMESTAMPTZ
);
-- BỔ SUNG
CREATE INDEX idx_conversation_sessions_user ON conversation_sessions(user_id);

CREATE TABLE conversation_turns (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_session_id UUID NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    turn_index      INT NOT NULL,
    user_audio_url  TEXT,
    user_transcript TEXT,
    corrected_transcript TEXT,             -- bản sửa ngữ pháp tự nhiên của lượt nói
    was_error_detected BOOLEAN DEFAULT false,
    pronunciation_score NUMERIC(5,2),       -- từ Azure Pronunciation Assessment
    pronunciation_advice TEXT,
    intent_score    NUMERIC(5,2),           -- mức phù hợp ý định giao tiếp (Mức 2 mở rộng, có thể null nếu chưa triển khai)
    politeness_score NUMERIC(5,2),
    cefr_tip        JSONB,                  -- {originalPhrase, betterPhrase, explanation}
    grammar_tip     TEXT,
    ai_response_text  TEXT,
    ai_response_audio_url TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_turns_session ON conversation_turns(conversation_session_id);

-- ============================================================
-- MỨC 3 — Nâng cấp streaming thời gian thực (mở rộng tương lai)
-- ============================================================

CREATE TABLE realtime_conversation_metrics (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_session_id UUID NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    avg_latency_ms  INT,
    interruption_count INT DEFAULT 0,
    stream_status   VARCHAR(20)             -- 'stable' | 'degraded' | 'failed'
);

-- ============================================================
-- MỨC 2/3 — Movie Delivery Context (real video ưu tiên, AI-generated dự phòng)
-- ============================================================

-- Nguồn thật: index từ video có phụ đề đã được cấp phép/công khai hợp lệ
CREATE TABLE video_sources (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title           VARCHAR(255),
    platform        VARCHAR(30),            -- 'youtube' | 'licensed_library'
    video_url       TEXT NOT NULL,
    subtitle_language VARCHAR(10) DEFAULT 'en'
);

CREATE TABLE video_subtitle_index (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_source_id UUID NOT NULL REFERENCES video_sources(id) ON DELETE CASCADE,
    phrase_text     TEXT NOT NULL,
    start_time_ms   INT NOT NULL,
    end_time_ms     INT NOT NULL
);
CREATE INDEX idx_subtitle_phrase ON video_subtitle_index USING gin (to_tsvector('english', phrase_text));

-- Dự phòng: khi không tìm được video thật khớp cụm từ, chỉ đọc mẫu câu bằng TTS
-- để người dùng nghe và luyện đọc nhại (shadowing) theo — không bịa cảnh phim.
CREATE TABLE movie_context_tts_fallback (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phrase_text     TEXT NOT NULL,
    persona_id      UUID REFERENCES personas(id),  -- giọng dùng để đọc mẫu chuẩn
    audio_url       TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    -- BỔ SUNG: tránh gọi lại Azure TTS sinh trùng audio cho cùng 1 cụm từ + giọng đọc
    -- (tiết kiệm chi phí API — movie_context_service phải SELECT trước khi INSERT)
    CONSTRAINT uq_tts_fallback_phrase_persona UNIQUE (phrase_text, persona_id)
);

-- Bảng kết quả tìm kiếm hợp nhất: mỗi kết quả CHỈ thuộc 1 trong 2 nguồn trên
CREATE TABLE movie_context_matches (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    search_phrase   VARCHAR(255) NOT NULL,
    source_type     VARCHAR(20) NOT NULL,   -- 'real_video' | 'tts_fallback'
    video_subtitle_index_id UUID REFERENCES video_subtitle_index(id),
    tts_fallback_id UUID REFERENCES movie_context_tts_fallback(id),
    is_saved        BOOLEAN DEFAULT false,  -- tính năng bookmark quan sát được ở prototype
    created_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_exactly_one_source CHECK (
        (source_type = 'real_video' AND video_subtitle_index_id IS NOT NULL AND tts_fallback_id IS NULL)
        OR
        (source_type = 'tts_fallback' AND tts_fallback_id IS NOT NULL AND video_subtitle_index_id IS NULL)
    )
);
CREATE INDEX idx_movie_matches_user ON movie_context_matches(user_id, is_saved);

-- ============================================================
-- NHÓM LÕI: LỖI XUYÊN SUỐT + ÔN TẬP THÍCH ỨNG (dùng chung mọi tính năng)
-- ============================================================

CREATE TABLE error_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_type      VARCHAR(20) NOT NULL,   -- 'vocab' | 'grammar' | 'pronunciation' | 'listening' | 'intent'
    source_table    VARCHAR(50) NOT NULL,   -- tên bảng gốc sinh ra lỗi (vd: 'writing_insights')
    source_id       UUID NOT NULL,          -- id bản ghi gốc
    error_detail    JSONB,
    severity        SMALLINT DEFAULT 1,     -- 1-5
    spaced_repetition_level SMALLINT DEFAULT 1, -- mức ôn tập đơn giản (khác SM-2 đầy đủ của vocab_reviews)
    created_at      TIMESTAMPTZ DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);
CREATE INDEX idx_error_log_user ON error_log(user_id, resolved_at);

-- Tổng hợp điểm theo từng kỹ năng cho Dashboard/Analytics (Nghe/Đọc/Viết/Nói + CEFR level riêng từng kỹ năng)
CREATE TABLE skill_progress (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_name      VARCHAR(30) NOT NULL,   -- 'listening' | 'reading' | 'writing' | 'speaking'
    cefr_level      VARCHAR(20),            -- 'C1 Advanced', 'B1 Intermediate'...
    score           NUMERIC(5,2),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, skill_name)
);

-- BỔ SUNG: trigger tự cập nhật updated_at mỗi lần điểm kỹ năng thay đổi
CREATE TRIGGER trg_skill_progress_updated_at
    BEFORE UPDATE ON skill_progress
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TABLE review_priority_queue (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_type       VARCHAR(20) NOT NULL,   -- 'vocab' | 'error_log'
    item_id         UUID NOT NULL,
    priority_score  NUMERIC(6,2) NOT NULL,
    last_calculated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_priority_user ON review_priority_queue(user_id, priority_score DESC);

CREATE TABLE quizzes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generated_from_error_ids UUID[],        -- các error_log.id dùng để sinh đề
    questions       JSONB NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- BỔ SUNG
CREATE INDEX idx_quizzes_user ON quizzes(user_id);

CREATE TABLE quiz_attempts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quiz_id         UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    answers         JSONB,
    score           NUMERIC(5,2),
    completed_at    TIMESTAMPTZ DEFAULT now()
);
-- BỔ SUNG
CREATE INDEX idx_quiz_attempts_user ON quiz_attempts(user_id);
CREATE INDEX idx_quiz_attempts_quiz ON quiz_attempts(quiz_id);

-- ============================================================
-- GAMIFICATION
-- ============================================================

CREATE TABLE streaks (
    user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    current_streak  INT DEFAULT 0,
    longest_streak  INT DEFAULT 0,
    last_active_date DATE
);