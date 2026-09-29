-- ============================================================================
-- schema.sql — bản chụp CHÍNH XÁC schema Postgres đang chạy thật của Lumina
-- (sinh bằng `pg_dump --schema-only`, KHÔNG viết tay).
--
-- MỤC ĐÍCH: đây là script `docker-entrypoint-initdb.d` chạy đúng 1 LẦN DUY NHẤT
-- khi volume `postgres_data` được tạo lần đầu (xem docker-compose.yml). Toàn bộ
-- migration Alembic trong backend/migrations/versions/ đều được viết idempotent
-- (luôn kiểm tra bảng/cột đã tồn tại trước khi tạo — xem comment đầu mỗi file
-- migration), nên dù volume được khởi tạo từ file này (đã có sẵn mọi cột mới
-- nhất) hay từ 1 bản schema.sql cũ hơn, chạy `alembic upgrade head` sau đó
-- LUÔN thành công, không bao giờ lỗi — chỉ là số lượng thao tác ALTER thực sự
-- chạy sẽ khác nhau tuỳ điểm xuất phát.
--
-- QUY ƯỚC BẮT BUỘC (đã thống nhất với người dùng 2026-09-17): mỗi khi có
-- migration Alembic mới làm thay đổi schema thật, file này PHẢI được cập nhật
-- lại (sinh lại bằng pg_dump) ngay trong cùng phiên làm việc đó, để file luôn
-- phản ánh đúng trạng thái DB mới nhất — không để lệch như đã từng xảy ra
-- trước đây (xem lumina_context.md mục 3.13, mục 4 điểm 11). Trước khi áp dụng
-- bất kỳ thay đổi schema DB mới nào, LUÔN thông báo và xin phép người dùng
-- trước khi chạy migration — không tự ý chạy `alembic upgrade` một mình.
--
-- Cách sinh lại file này khi cần:
--   docker exec lumina_db pg_dump -U lumina_user -d lumina_db --schema-only \
--     --no-owner --no-privileges --exclude-table=alembic_version
--   (rồi bỏ dòng `\restrict`/`\unrestrict` và các dòng `SET ...`/
--   `SELECT pg_catalog.set_config...` ở đầu file — chỉ là cấu hình phiên
--   pg_dump/pg_restore, không cần thiết khi chạy qua psql -f lúc init container).
--
-- Thiết kế mục tiêu đầy đủ (kèm rationale cho từng quyết định ON DELETE/CHECK)
-- vẫn nằm ở docs/schema.sql — file đó dùng để đọc hiểu/bảo vệ khóa luận, KHÔNG
-- dùng để khởi tạo DB (2 file có thể tạm lệch nhau về câu chữ/tổ chức, nhưng
-- file .sql ở đây luôn là nguồn đúng về mặt DDL thực thi được).
--
-- Sinh lần cuối: 2026-09-28, khớp Alembic revision 20260927_0018 (thêm users.timer_mode_enabled + bảng study_time_log cho Dashboard "This week, in minutes"/"Pick up where you left off").
-- ============================================================================

--
-- PostgreSQL database dump
--


-- Dumped from database version 16.15 (Debian 16.15-1.pgdg12+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg12+2)


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;




--
-- Name: contextual_guess_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contextual_guess_attempts (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    vocab_item_id uuid,
    term character varying(100) NOT NULL,
    challenge_sentence text NOT NULL,
    options jsonb NOT NULL,
    correct_option_index smallint NOT NULL,
    selected_option_index smallint,
    is_correct boolean,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: conversation_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversation_sessions (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    scenario_id uuid,
    persona_id uuid,
    status character varying(20) DEFAULT 'in_progress'::character varying,
    started_at timestamp with time zone DEFAULT now(),
    ended_at timestamp with time zone,
    CONSTRAINT chk_conversation_sessions_status_valid CHECK (((status)::text = ANY ((ARRAY['in_progress'::character varying, 'completed'::character varying, 'expired'::character varying])::text[])))
);


--
-- Name: conversation_turns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversation_turns (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    conversation_session_id uuid NOT NULL,
    turn_index integer NOT NULL,
    user_audio_url text,
    user_transcript text,
    corrected_transcript text,
    was_error_detected boolean DEFAULT false,
    pronunciation_score numeric(5,2),
    pronunciation_advice text,
    intent_score numeric(5,2),
    politeness_score numeric(5,2),
    cefr_tip jsonb,
    grammar_tip text,
    ai_response_text text,
    ai_response_audio_url text,
    created_at timestamp with time zone DEFAULT now(),
    stt_provider_used character varying(20),
    pronunciation_assessment_failed boolean DEFAULT false NOT NULL,
    intent_feedback text,
    politeness_feedback text,
    suggested_phrases jsonb
);


--
-- Name: custom_stories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.custom_stories (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    vocab_item_ids uuid[] NOT NULL,
    generated_text text NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: dictation_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dictation_attempts (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    podcast_id uuid NOT NULL,
    user_input_text text NOT NULL,
    diff_result jsonb,
    accuracy_score numeric(5,2),
    created_at timestamp with time zone DEFAULT now(),
    start_word_index integer,
    end_word_index integer,
    audio_segment_path text,
    reference_word_tags jsonb DEFAULT '[]'::jsonb NOT NULL
);


--
-- Name: document_chunks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_chunks (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    document_id uuid NOT NULL,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    embedding public.vector(768),
    page_or_line_ref character varying(50),
    token_count integer,
    created_at timestamp with time zone DEFAULT now(),
    embedding_local public.vector(1024)
);


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    folder_id uuid,
    title character varying(255) NOT NULL,
    source_type character varying(20) NOT NULL,
    source_url text,
    file_path text,
    file_size_kb integer,
    tags text[],
    starred boolean DEFAULT false,
    language character varying(10) DEFAULT 'en'::character varying,
    status character varying(20) DEFAULT 'processing'::character varying,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT chk_documents_source_type_valid CHECK (((source_type)::text = ANY ((ARRAY['audio'::character varying, 'docx'::character varying])::text[]))),
    CONSTRAINT chk_documents_status_valid CHECK (((status)::text = ANY ((ARRAY['processing'::character varying, 'ready'::character varying, 'failed'::character varying])::text[])))
);


--
-- Name: generated_passages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.generated_passages (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    topic character varying(100),
    level character varying(10),
    title character varying(255),
    content text NOT NULL,
    read_time_label character varying(20),
    word_count_label character varying(20),
    target_vocab_words text[],
    created_at timestamp with time zone DEFAULT now(),
    source_document_id uuid
);


--
-- Name: movie_context_matches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.movie_context_matches (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    search_phrase character varying(255) NOT NULL,
    source_type character varying(20) NOT NULL,
    video_subtitle_index_id uuid,
    tts_fallback_id uuid,
    is_saved boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT chk_exactly_one_source CHECK (((((source_type)::text = 'real_video'::text) AND (video_subtitle_index_id IS NOT NULL) AND (tts_fallback_id IS NULL)) OR (((source_type)::text = 'tts_fallback'::text) AND (tts_fallback_id IS NOT NULL) AND (video_subtitle_index_id IS NULL))))
);


--
-- Name: movie_context_tts_fallback; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.movie_context_tts_fallback (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    phrase_text text NOT NULL,
    persona_id uuid,
    audio_url text NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: notebook_chat_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notebook_chat_messages (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    document_id uuid NOT NULL,
    user_id uuid NOT NULL,
    role character varying(10) NOT NULL,
    content text NOT NULL,
    sources jsonb,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT chk_notebook_chat_role_valid CHECK (((role)::text = ANY ((ARRAY['user'::character varying, 'assistant'::character varying])::text[])))
);


--
-- Name: notebook_folders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notebook_folders (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    name character varying(100) NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: personas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.personas (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    name character varying(100) NOT NULL,
    provider character varying(30) NOT NULL,
    voice_id character varying(100) NOT NULL,
    accent_tag character varying(30),
    description text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: podcasts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.podcasts (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    document_id uuid NOT NULL,
    script_text text NOT NULL,
    audio_url text,
    duration_seconds integer,
    created_at timestamp with time zone DEFAULT now(),
    persona_id uuid,
    status character varying(20) DEFAULT 'processing'::character varying NOT NULL,
    CONSTRAINT chk_podcasts_status_valid CHECK (((status)::text = ANY ((ARRAY['processing'::character varying, 'ready'::character varying, 'failed'::character varying])::text[])))
);


--
-- Name: quiz_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quiz_attempts (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    quiz_id uuid,
    user_id uuid NOT NULL,
    answers jsonb,
    score numeric(5,2),
    completed_at timestamp with time zone DEFAULT now(),
    attempt_type character varying(30),
    is_open_form boolean,
    payload jsonb,
    CONSTRAINT chk_quiz_attempts_attempt_type_valid CHECK (((attempt_type IS NULL) OR ((attempt_type)::text = ANY ((ARRAY['rearrange_reading'::character varying, 'rearrange_writing'::character varying])::text[]))))
);


--
-- Name: quizzes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quizzes (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    generated_from_error_ids uuid[],
    questions jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    focus_error_types jsonb
);


--
-- Name: reading_answers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reading_answers (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    reading_session_id uuid NOT NULL,
    question text NOT NULL,
    options jsonb NOT NULL,
    correct_option_index smallint NOT NULL,
    selected_option_index smallint,
    is_correct boolean,
    source_chunk_id uuid,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: reading_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reading_sessions (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    document_id uuid,
    generated_passage_id uuid,
    mode character varying(20) NOT NULL,
    score numeric(5,2),
    time_taken_seconds integer,
    created_at timestamp with time zone DEFAULT now(),
    completed_at timestamp with time zone,
    CONSTRAINT chk_reading_source CHECK (((((mode)::text = 'classic'::text) AND (document_id IS NOT NULL) AND (generated_passage_id IS NULL)) OR (((mode)::text = 'skim_scan'::text) AND (generated_passage_id IS NOT NULL) AND (document_id IS NULL))))
);


--
-- Name: realtime_conversation_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.realtime_conversation_metrics (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    conversation_session_id uuid NOT NULL,
    avg_latency_ms integer,
    interruption_count integer DEFAULT 0,
    stream_status character varying(20)
);


--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.refresh_tokens (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    token_hash character varying(255) NOT NULL,
    is_revoked boolean DEFAULT false,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    client_type character varying(20) DEFAULT 'web'::character varying NOT NULL,
    CONSTRAINT chk_refresh_tokens_client_type CHECK (((client_type)::text = ANY ((ARRAY['web'::character varying, 'extension'::character varying])::text[])))
);


--
-- Name: rephrase_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rephrase_requests (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    writing_submission_id uuid,
    original_text text NOT NULL,
    rephrased_text text NOT NULL,
    style_target character varying(20),
    created_at timestamp with time zone DEFAULT now(),
    explanation text
);


--
-- Name: review_priority_queue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.review_priority_queue (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    item_type character varying(20) NOT NULL,
    item_id uuid NOT NULL,
    priority_score numeric(6,2) NOT NULL,
    last_calculated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT chk_review_priority_item_type_valid CHECK (((item_type)::text = ANY ((ARRAY['vocab'::character varying, 'error'::character varying])::text[])))
);


--
-- Name: scenarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scenarios (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    title character varying(150) NOT NULL,
    description text,
    difficulty_level character varying(10),
    target_intents jsonb,
    goal text,
    formality_level character varying(20) DEFAULT 'neutral'::character varying NOT NULL
);


--
-- Name: skill_progress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.skill_progress (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    skill_name character varying(30) NOT NULL,
    cefr_level character varying(20),
    score numeric(5,2),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT chk_skill_progress_skill_valid CHECK (((skill_name)::text = ANY ((ARRAY['reading'::character varying, 'listening'::character varying, 'writing'::character varying, 'speaking'::character varying])::text[])))
);


--
-- Name: slang_phrases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.slang_phrases (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    phrase_text character varying(150) NOT NULL,
    meaning text NOT NULL,
    example_sentence text,
    formality_level character varying(20) DEFAULT 'neutral'::character varying NOT NULL,
    topic_tags character varying[],
    source_reference character varying(150) NOT NULL,
    CONSTRAINT ck_slang_source_not_empty CHECK (((source_reference)::text <> ''::text))
);


--
-- Name: streaks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.streaks (
    user_id uuid NOT NULL,
    current_streak integer DEFAULT 0,
    longest_streak integer DEFAULT 0,
    last_active_date date,
    total_xp integer DEFAULT 0
);


--
-- Name: study_time_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.study_time_log (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    skill character varying(20) NOT NULL,
    duration_seconds integer NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT chk_study_time_log_duration_positive CHECK ((duration_seconds > 0)),
    CONSTRAINT chk_study_time_log_skill_valid CHECK (((skill)::text = ANY ((ARRAY['reading'::character varying, 'listening'::character varying, 'writing'::character varying, 'speaking'::character varying])::text[])))
);


--
-- Name: transcript_segments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transcript_segments (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    podcast_id uuid NOT NULL,
    word_index integer NOT NULL,
    word_text character varying(100) NOT NULL,
    start_time_ms integer NOT NULL,
    end_time_ms integer NOT NULL
);


--
-- Name: user_errors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_errors (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    quiz_attempt_id uuid,
    error_type character varying(30) NOT NULL,
    spaced_repetition_level integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    detail jsonb,
    CONSTRAINT chk_user_errors_error_type_valid CHECK (((error_type)::text = ANY ((ARRAY['grammar'::character varying, 'vocabulary'::character varying, 'spelling'::character varying, 'pronunciation'::character varying, 'listening_comprehension'::character varying, 'reading_comprehension'::character varying, 'writing_coherence'::character varying, 'communicative_intent'::character varying, 'politeness'::character varying])::text[])))
);


--
-- Name: user_phrasebook_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_phrasebook_entries (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    slang_phrase_id uuid,
    conversation_turn_id uuid,
    phrase_text character varying(150) NOT NULL,
    meaning text,
    example_sentence text,
    formality_level character varying(20),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    display_name character varying(100),
    native_language character varying(10) DEFAULT 'vi'::character varying,
    target_level character varying(10),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    timer_mode_enabled boolean DEFAULT false NOT NULL
);


--
-- Name: video_sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.video_sources (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    title character varying(255),
    platform character varying(30),
    video_url text NOT NULL,
    subtitle_language character varying(10) DEFAULT 'en'::character varying
);


--
-- Name: video_subtitle_index; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.video_subtitle_index (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    video_source_id uuid NOT NULL,
    phrase_text text NOT NULL,
    start_time_ms integer NOT NULL,
    end_time_ms integer NOT NULL
);


--
-- Name: vocab_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vocab_items (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    document_id uuid,
    term character varying(100) NOT NULL,
    ipa character varying(100),
    part_of_speech character varying(30),
    definition text,
    example_sentence text,
    synonyms text[],
    antonyms text[],
    created_at timestamp with time zone DEFAULT now(),
    source_url text,
    CONSTRAINT chk_vocab_source_exactly_one CHECK ((NOT ((document_id IS NOT NULL) AND (source_url IS NOT NULL))))
);


--
-- Name: vocab_reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vocab_reviews (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    vocab_item_id uuid NOT NULL,
    ease_factor numeric(4,2) DEFAULT 2.5,
    interval_days integer DEFAULT 1,
    repetitions integer DEFAULT 0,
    last_grade smallint,
    last_reviewed_at timestamp with time zone,
    next_review_at timestamp with time zone DEFAULT now()
);


--
-- Name: writing_insights; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.writing_insights (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    writing_submission_id uuid NOT NULL,
    insight_type character varying(20) NOT NULL,
    title character varying(150) NOT NULL,
    description text NOT NULL,
    original_text text,
    suggested_text text,
    error_start_offset integer,
    error_end_offset integer,
    rule text,
    synonyms jsonb,
    suggestion text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT chk_writing_insights_type_valid CHECK (((insight_type)::text = ANY ((ARRAY['grammar'::character varying, 'vocabulary'::character varying, 'style'::character varying])::text[])))
);


--
-- Name: writing_submissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.writing_submissions (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    document_id uuid,
    title character varying(255),
    submitted_text text NOT NULL,
    overall_score numeric(5,2),
    cefr_level character varying(15),
    ielts_band character varying(15),
    created_at timestamp with time zone DEFAULT now(),
    source_type character varying(20) DEFAULT 'document_summary'::character varying NOT NULL,
    prompt_text text,
    certificate_style character varying(20),
    rubric_scores jsonb,
    completed_at timestamp with time zone,
    CONSTRAINT chk_writing_certificate_style_valid CHECK (((certificate_style IS NULL) OR ((certificate_style)::text = ANY ((ARRAY['toeic'::character varying, 'ielts'::character varying, 'cambridge'::character varying])::text[])))),
    CONSTRAINT chk_writing_document_id_by_source CHECK ((((source_type)::text <> 'free_topic'::text) OR (document_id IS NULL))),
    CONSTRAINT chk_writing_source_type_valid CHECK (((source_type)::text = ANY ((ARRAY['document_summary'::character varying, 'extended_topic'::character varying, 'free_topic'::character varying])::text[])))
);


--
-- Name: contextual_guess_attempts contextual_guess_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contextual_guess_attempts
    ADD CONSTRAINT contextual_guess_attempts_pkey PRIMARY KEY (id);


--
-- Name: conversation_sessions conversation_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_sessions
    ADD CONSTRAINT conversation_sessions_pkey PRIMARY KEY (id);


--
-- Name: conversation_turns conversation_turns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_turns
    ADD CONSTRAINT conversation_turns_pkey PRIMARY KEY (id);


--
-- Name: custom_stories custom_stories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_stories
    ADD CONSTRAINT custom_stories_pkey PRIMARY KEY (id);


--
-- Name: dictation_attempts dictation_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dictation_attempts
    ADD CONSTRAINT dictation_attempts_pkey PRIMARY KEY (id);


--
-- Name: document_chunks document_chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT document_chunks_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: generated_passages generated_passages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.generated_passages
    ADD CONSTRAINT generated_passages_pkey PRIMARY KEY (id);


--
-- Name: movie_context_matches movie_context_matches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movie_context_matches
    ADD CONSTRAINT movie_context_matches_pkey PRIMARY KEY (id);


--
-- Name: movie_context_tts_fallback movie_context_tts_fallback_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movie_context_tts_fallback
    ADD CONSTRAINT movie_context_tts_fallback_pkey PRIMARY KEY (id);


--
-- Name: notebook_chat_messages notebook_chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notebook_chat_messages
    ADD CONSTRAINT notebook_chat_messages_pkey PRIMARY KEY (id);


--
-- Name: notebook_folders notebook_folders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notebook_folders
    ADD CONSTRAINT notebook_folders_pkey PRIMARY KEY (id);


--
-- Name: personas personas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personas
    ADD CONSTRAINT personas_pkey PRIMARY KEY (id);


--
-- Name: podcasts podcasts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.podcasts
    ADD CONSTRAINT podcasts_pkey PRIMARY KEY (id);


--
-- Name: quiz_attempts quiz_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_attempts
    ADD CONSTRAINT quiz_attempts_pkey PRIMARY KEY (id);


--
-- Name: quizzes quizzes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quizzes
    ADD CONSTRAINT quizzes_pkey PRIMARY KEY (id);


--
-- Name: reading_answers reading_answers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_answers
    ADD CONSTRAINT reading_answers_pkey PRIMARY KEY (id);


--
-- Name: reading_sessions reading_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_sessions
    ADD CONSTRAINT reading_sessions_pkey PRIMARY KEY (id);


--
-- Name: realtime_conversation_metrics realtime_conversation_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.realtime_conversation_metrics
    ADD CONSTRAINT realtime_conversation_metrics_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_token_hash_key UNIQUE (token_hash);


--
-- Name: rephrase_requests rephrase_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rephrase_requests
    ADD CONSTRAINT rephrase_requests_pkey PRIMARY KEY (id);


--
-- Name: review_priority_queue review_priority_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_priority_queue
    ADD CONSTRAINT review_priority_queue_pkey PRIMARY KEY (id);


--
-- Name: scenarios scenarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scenarios
    ADD CONSTRAINT scenarios_pkey PRIMARY KEY (id);


--
-- Name: skill_progress skill_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_progress
    ADD CONSTRAINT skill_progress_pkey PRIMARY KEY (id);


--
-- Name: skill_progress skill_progress_user_id_skill_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_progress
    ADD CONSTRAINT skill_progress_user_id_skill_name_key UNIQUE (user_id, skill_name);


--
-- Name: slang_phrases slang_phrases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.slang_phrases
    ADD CONSTRAINT slang_phrases_pkey PRIMARY KEY (id);


--
-- Name: streaks streaks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.streaks
    ADD CONSTRAINT streaks_pkey PRIMARY KEY (user_id);


--
-- Name: study_time_log study_time_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_time_log
    ADD CONSTRAINT study_time_log_pkey PRIMARY KEY (id);


--
-- Name: transcript_segments transcript_segments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcript_segments
    ADD CONSTRAINT transcript_segments_pkey PRIMARY KEY (id);


--
-- Name: movie_context_tts_fallback uq_tts_fallback_phrase_persona; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movie_context_tts_fallback
    ADD CONSTRAINT uq_tts_fallback_phrase_persona UNIQUE (phrase_text, persona_id);


--
-- Name: user_errors user_errors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_errors
    ADD CONSTRAINT user_errors_pkey PRIMARY KEY (id);


--
-- Name: user_phrasebook_entries user_phrasebook_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_phrasebook_entries
    ADD CONSTRAINT user_phrasebook_entries_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: video_sources video_sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_sources
    ADD CONSTRAINT video_sources_pkey PRIMARY KEY (id);


--
-- Name: video_subtitle_index video_subtitle_index_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_subtitle_index
    ADD CONSTRAINT video_subtitle_index_pkey PRIMARY KEY (id);


--
-- Name: vocab_items vocab_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocab_items
    ADD CONSTRAINT vocab_items_pkey PRIMARY KEY (id);


--
-- Name: vocab_reviews vocab_reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocab_reviews
    ADD CONSTRAINT vocab_reviews_pkey PRIMARY KEY (id);


--
-- Name: vocab_reviews vocab_reviews_vocab_item_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocab_reviews
    ADD CONSTRAINT vocab_reviews_vocab_item_id_key UNIQUE (vocab_item_id);


--
-- Name: writing_insights writing_insights_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.writing_insights
    ADD CONSTRAINT writing_insights_pkey PRIMARY KEY (id);


--
-- Name: writing_submissions writing_submissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.writing_submissions
    ADD CONSTRAINT writing_submissions_pkey PRIMARY KEY (id);


--
-- Name: idx_chunks_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chunks_document ON public.document_chunks USING btree (document_id);


--
-- Name: idx_chunks_embedding_hnsw; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chunks_embedding_hnsw ON public.document_chunks USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_chunks_embedding_local_hnsw; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chunks_embedding_local_hnsw ON public.document_chunks USING hnsw (embedding_local public.vector_cosine_ops);


--
-- Name: idx_contextual_guess_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contextual_guess_user ON public.contextual_guess_attempts USING btree (user_id);


--
-- Name: idx_contextual_guess_vocab_item; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contextual_guess_vocab_item ON public.contextual_guess_attempts USING btree (vocab_item_id);


--
-- Name: idx_conversation_sessions_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversation_sessions_user ON public.conversation_sessions USING btree (user_id);


--
-- Name: idx_custom_stories_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_custom_stories_user ON public.custom_stories USING btree (user_id);


--
-- Name: idx_dictation_attempts_podcast; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dictation_attempts_podcast ON public.dictation_attempts USING btree (podcast_id);


--
-- Name: idx_dictation_attempts_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dictation_attempts_user ON public.dictation_attempts USING btree (user_id);


--
-- Name: idx_documents_folder; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_folder ON public.documents USING btree (folder_id);


--
-- Name: idx_documents_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_user ON public.documents USING btree (user_id);


--
-- Name: idx_generated_passages_source_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_generated_passages_source_document ON public.generated_passages USING btree (source_document_id);


--
-- Name: idx_generated_passages_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_generated_passages_user ON public.generated_passages USING btree (user_id);


--
-- Name: idx_movie_matches_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_movie_matches_user ON public.movie_context_matches USING btree (user_id, is_saved);


--
-- Name: idx_notebook_chat_messages_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notebook_chat_messages_document ON public.notebook_chat_messages USING btree (document_id, created_at);


--
-- Name: idx_notebook_folders_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notebook_folders_user ON public.notebook_folders USING btree (user_id);


--
-- Name: idx_phrasebook_conversation_turn; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_phrasebook_conversation_turn ON public.user_phrasebook_entries USING btree (conversation_turn_id);


--
-- Name: idx_phrasebook_slang_phrase; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_phrasebook_slang_phrase ON public.user_phrasebook_entries USING btree (slang_phrase_id);


--
-- Name: idx_phrasebook_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_phrasebook_user ON public.user_phrasebook_entries USING btree (user_id);


--
-- Name: idx_podcasts_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_podcasts_document ON public.podcasts USING btree (document_id);


--
-- Name: idx_priority_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_priority_user ON public.review_priority_queue USING btree (user_id, priority_score DESC);


--
-- Name: idx_quiz_attempts_quiz; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quiz_attempts_quiz ON public.quiz_attempts USING btree (quiz_id);


--
-- Name: idx_quiz_attempts_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quiz_attempts_user ON public.quiz_attempts USING btree (user_id);


--
-- Name: idx_quizzes_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quizzes_user ON public.quizzes USING btree (user_id);


--
-- Name: idx_reading_answers_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reading_answers_session ON public.reading_answers USING btree (reading_session_id);


--
-- Name: idx_reading_answers_source_chunk; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reading_answers_source_chunk ON public.reading_answers USING btree (source_chunk_id);


--
-- Name: idx_reading_sessions_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reading_sessions_document ON public.reading_sessions USING btree (document_id);


--
-- Name: idx_reading_sessions_passage; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reading_sessions_passage ON public.reading_sessions USING btree (generated_passage_id);


--
-- Name: idx_reading_sessions_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reading_sessions_user ON public.reading_sessions USING btree (user_id);


--
-- Name: idx_refresh_tokens_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_refresh_tokens_user ON public.refresh_tokens USING btree (user_id);


--
-- Name: idx_rephrase_requests_submission; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rephrase_requests_submission ON public.rephrase_requests USING btree (writing_submission_id);


--
-- Name: idx_study_time_log_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_study_time_log_user_created ON public.study_time_log USING btree (user_id, created_at);


--
-- Name: idx_subtitle_phrase; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_subtitle_phrase ON public.video_subtitle_index USING gin (to_tsvector('english'::regconfig, phrase_text));


--
-- Name: idx_transcript_podcast; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transcript_podcast ON public.transcript_segments USING btree (podcast_id);


--
-- Name: idx_turns_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_turns_session ON public.conversation_turns USING btree (conversation_session_id);


--
-- Name: idx_user_errors_quiz_attempt; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_errors_quiz_attempt ON public.user_errors USING btree (quiz_attempt_id);


--
-- Name: idx_user_errors_user_id_error_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_errors_user_id_error_type ON public.user_errors USING btree (user_id, error_type);


--
-- Name: idx_vocab_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vocab_document ON public.vocab_items USING btree (document_id);


--
-- Name: idx_vocab_reviews_next; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vocab_reviews_next ON public.vocab_reviews USING btree (next_review_at);


--
-- Name: idx_vocab_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vocab_user ON public.vocab_items USING btree (user_id);


--
-- Name: idx_writing_insights_submission; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_writing_insights_submission ON public.writing_insights USING btree (writing_submission_id);


--
-- Name: idx_writing_submissions_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_writing_submissions_document ON public.writing_submissions USING btree (document_id);


--
-- Name: idx_writing_submissions_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_writing_submissions_user ON public.writing_submissions USING btree (user_id);


--
-- Name: uq_conversation_turns_session_turn; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_conversation_turns_session_turn ON public.conversation_turns USING btree (conversation_session_id, turn_index);


--
-- Name: uq_transcript_segments_podcast_word; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_transcript_segments_podcast_word ON public.transcript_segments USING btree (podcast_id, word_index);


--
-- Name: uq_vocab_items_user_term; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_vocab_items_user_term ON public.vocab_items USING btree (user_id, lower((term)::text));


--
-- Name: skill_progress trg_skill_progress_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_skill_progress_updated_at BEFORE UPDATE ON public.skill_progress FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: users trg_users_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: contextual_guess_attempts contextual_guess_attempts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contextual_guess_attempts
    ADD CONSTRAINT contextual_guess_attempts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: contextual_guess_attempts contextual_guess_attempts_vocab_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contextual_guess_attempts
    ADD CONSTRAINT contextual_guess_attempts_vocab_item_id_fkey FOREIGN KEY (vocab_item_id) REFERENCES public.vocab_items(id) ON DELETE SET NULL;


--
-- Name: conversation_sessions conversation_sessions_persona_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_sessions
    ADD CONSTRAINT conversation_sessions_persona_id_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id);


--
-- Name: conversation_sessions conversation_sessions_scenario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_sessions
    ADD CONSTRAINT conversation_sessions_scenario_id_fkey FOREIGN KEY (scenario_id) REFERENCES public.scenarios(id);


--
-- Name: conversation_sessions conversation_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_sessions
    ADD CONSTRAINT conversation_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: conversation_turns conversation_turns_conversation_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_turns
    ADD CONSTRAINT conversation_turns_conversation_session_id_fkey FOREIGN KEY (conversation_session_id) REFERENCES public.conversation_sessions(id) ON DELETE CASCADE;


--
-- Name: custom_stories custom_stories_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_stories
    ADD CONSTRAINT custom_stories_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: dictation_attempts dictation_attempts_podcast_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dictation_attempts
    ADD CONSTRAINT dictation_attempts_podcast_id_fkey FOREIGN KEY (podcast_id) REFERENCES public.podcasts(id) ON DELETE CASCADE;


--
-- Name: dictation_attempts dictation_attempts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dictation_attempts
    ADD CONSTRAINT dictation_attempts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: document_chunks document_chunks_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT document_chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: documents documents_folder_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_folder_id_fkey FOREIGN KEY (folder_id) REFERENCES public.notebook_folders(id) ON DELETE SET NULL;


--
-- Name: documents documents_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: generated_passages generated_passages_source_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.generated_passages
    ADD CONSTRAINT generated_passages_source_document_id_fkey FOREIGN KEY (source_document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: generated_passages generated_passages_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.generated_passages
    ADD CONSTRAINT generated_passages_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: movie_context_matches movie_context_matches_tts_fallback_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movie_context_matches
    ADD CONSTRAINT movie_context_matches_tts_fallback_id_fkey FOREIGN KEY (tts_fallback_id) REFERENCES public.movie_context_tts_fallback(id);


--
-- Name: movie_context_matches movie_context_matches_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movie_context_matches
    ADD CONSTRAINT movie_context_matches_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: movie_context_matches movie_context_matches_video_subtitle_index_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movie_context_matches
    ADD CONSTRAINT movie_context_matches_video_subtitle_index_id_fkey FOREIGN KEY (video_subtitle_index_id) REFERENCES public.video_subtitle_index(id);


--
-- Name: movie_context_tts_fallback movie_context_tts_fallback_persona_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movie_context_tts_fallback
    ADD CONSTRAINT movie_context_tts_fallback_persona_id_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id);


--
-- Name: notebook_chat_messages notebook_chat_messages_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notebook_chat_messages
    ADD CONSTRAINT notebook_chat_messages_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: notebook_chat_messages notebook_chat_messages_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notebook_chat_messages
    ADD CONSTRAINT notebook_chat_messages_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: notebook_folders notebook_folders_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notebook_folders
    ADD CONSTRAINT notebook_folders_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: podcasts podcasts_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.podcasts
    ADD CONSTRAINT podcasts_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: podcasts podcasts_persona_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.podcasts
    ADD CONSTRAINT podcasts_persona_id_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id) ON DELETE SET NULL;


--
-- Name: quiz_attempts quiz_attempts_quiz_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_attempts
    ADD CONSTRAINT quiz_attempts_quiz_id_fkey FOREIGN KEY (quiz_id) REFERENCES public.quizzes(id) ON DELETE CASCADE;


--
-- Name: quiz_attempts quiz_attempts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quiz_attempts
    ADD CONSTRAINT quiz_attempts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: quizzes quizzes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quizzes
    ADD CONSTRAINT quizzes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: reading_answers reading_answers_reading_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_answers
    ADD CONSTRAINT reading_answers_reading_session_id_fkey FOREIGN KEY (reading_session_id) REFERENCES public.reading_sessions(id) ON DELETE CASCADE;


--
-- Name: reading_answers reading_answers_source_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_answers
    ADD CONSTRAINT reading_answers_source_chunk_id_fkey FOREIGN KEY (source_chunk_id) REFERENCES public.document_chunks(id) ON DELETE SET NULL;


--
-- Name: reading_sessions reading_sessions_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_sessions
    ADD CONSTRAINT reading_sessions_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: reading_sessions reading_sessions_generated_passage_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_sessions
    ADD CONSTRAINT reading_sessions_generated_passage_id_fkey FOREIGN KEY (generated_passage_id) REFERENCES public.generated_passages(id) ON DELETE CASCADE;


--
-- Name: reading_sessions reading_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reading_sessions
    ADD CONSTRAINT reading_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: realtime_conversation_metrics realtime_conversation_metrics_conversation_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.realtime_conversation_metrics
    ADD CONSTRAINT realtime_conversation_metrics_conversation_session_id_fkey FOREIGN KEY (conversation_session_id) REFERENCES public.conversation_sessions(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: rephrase_requests rephrase_requests_writing_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rephrase_requests
    ADD CONSTRAINT rephrase_requests_writing_submission_id_fkey FOREIGN KEY (writing_submission_id) REFERENCES public.writing_submissions(id) ON DELETE CASCADE;


--
-- Name: review_priority_queue review_priority_queue_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_priority_queue
    ADD CONSTRAINT review_priority_queue_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: skill_progress skill_progress_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_progress
    ADD CONSTRAINT skill_progress_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: streaks streaks_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.streaks
    ADD CONSTRAINT streaks_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: study_time_log study_time_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.study_time_log
    ADD CONSTRAINT study_time_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: transcript_segments transcript_segments_podcast_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcript_segments
    ADD CONSTRAINT transcript_segments_podcast_id_fkey FOREIGN KEY (podcast_id) REFERENCES public.podcasts(id) ON DELETE CASCADE;


--
-- Name: user_errors user_errors_quiz_attempt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_errors
    ADD CONSTRAINT user_errors_quiz_attempt_id_fkey FOREIGN KEY (quiz_attempt_id) REFERENCES public.quiz_attempts(id) ON DELETE SET NULL;


--
-- Name: user_errors user_errors_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_errors
    ADD CONSTRAINT user_errors_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_phrasebook_entries user_phrasebook_entries_conversation_turn_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_phrasebook_entries
    ADD CONSTRAINT user_phrasebook_entries_conversation_turn_id_fkey FOREIGN KEY (conversation_turn_id) REFERENCES public.conversation_turns(id) ON DELETE SET NULL;


--
-- Name: user_phrasebook_entries user_phrasebook_entries_slang_phrase_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_phrasebook_entries
    ADD CONSTRAINT user_phrasebook_entries_slang_phrase_id_fkey FOREIGN KEY (slang_phrase_id) REFERENCES public.slang_phrases(id) ON DELETE SET NULL;


--
-- Name: user_phrasebook_entries user_phrasebook_entries_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_phrasebook_entries
    ADD CONSTRAINT user_phrasebook_entries_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: video_subtitle_index video_subtitle_index_video_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.video_subtitle_index
    ADD CONSTRAINT video_subtitle_index_video_source_id_fkey FOREIGN KEY (video_source_id) REFERENCES public.video_sources(id) ON DELETE CASCADE;


--
-- Name: vocab_items vocab_items_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocab_items
    ADD CONSTRAINT vocab_items_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: vocab_items vocab_items_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocab_items
    ADD CONSTRAINT vocab_items_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: vocab_reviews vocab_reviews_vocab_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vocab_reviews
    ADD CONSTRAINT vocab_reviews_vocab_item_id_fkey FOREIGN KEY (vocab_item_id) REFERENCES public.vocab_items(id) ON DELETE CASCADE;


--
-- Name: writing_insights writing_insights_writing_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.writing_insights
    ADD CONSTRAINT writing_insights_writing_submission_id_fkey FOREIGN KEY (writing_submission_id) REFERENCES public.writing_submissions(id) ON DELETE CASCADE;


--
-- Name: writing_submissions writing_submissions_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.writing_submissions
    ADD CONSTRAINT writing_submissions_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: writing_submissions writing_submissions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.writing_submissions
    ADD CONSTRAINT writing_submissions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--


