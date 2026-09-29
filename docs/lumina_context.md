# Lumina — Context File (Khóa luận tốt nghiệp)

> File này là bản tổng hợp trạng thái dự án tính đến thời điểm hiện tại. Khi bắt đầu phiên làm việc mới, upload file này (kèm `de_cuong_khoa_luan.md` nếu cần) để Claude nắm lại toàn bộ ngữ cảnh và tiếp tục đúng flow, không lặp lại các quyết định đã chốt.

---

## 1. Tổng quan dự án

**Lumina** — nền tảng học tiếng Anh tích hợp AI, đồ án tốt nghiệp CNTT. Bao phủ 4 kỹ năng: **Reading, Writing, Listening, Speaking**.

**Ràng buộc xuyên suốt (quan trọng nhất):** Kỷ luật về phạm vi (scope discipline). Mọi feature phải:
- Bảo vệ được về mặt học thuật (academically defensible)
- Có backend implementation thực sự chạy được
- Được phân tầng rõ ràng theo 3 mức (tên gọi hiện dùng trong đề cương chính thức):
  - **Đầy đủ (MVP)**: Core, implement đầy đủ
  - **Thử nghiệm giới hạn (Experimental)**: Implement quy mô nhỏ, có caveat, hoặc cần subsystem mới
  - **Định hướng mở rộng (Proof-of-concept / Future direction)**: Chỉ định hướng, không build đầy đủ

**Tiêu chí thành công**: Khóa luận mạch lạc, bảo vệ được, có backend hoạt động chứng minh AI integration thật trên cả 4 kỹ năng.

**Tên đề tài**: chưa chốt chính thức — hiện có 1 phương án khuyến nghị + 3 phương án thay thế trong `de_cuong_khoa_luan.md` mục 1.

---

## 2. Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Backend framework | FastAPI |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL + pgvector (single DB, không dùng vector store riêng như ChromaDB) |
| LLM abstraction | Gọi thẳng SDK `google-generativeai` (không qua LangChain). Embedding: mặc định bge-m3 qua Ollama (`embedding_local`, 1024-dim); `EMBEDDING_PROVIDER=gemini` dùng `gemini-embedding-001` (`embedding`, 768-dim) |
| STT + Pronunciation Assessment | Azure Cognitive Services (**Pronunciation Assessment bắt buộc, không thể thay thế**) |
| STT dự phòng (fallback) | OpenAI Whisper API — **chỉ** dùng khi Azure STT lỗi/timeout ở nhánh STT thuần của Speaking; không thay thế Azure Pronunciation Assessment (mục 3.8) |
| TTS | ElevenLabs |
| Migration | Alembic |
| Auth | JWT — `passlib[bcrypt]` + `python-jose` |
| Extension | Chrome Manifest V3 |
| Đầu vào tài liệu | **Giới hạn nghiêm ngặt: chỉ audio và .docx** — không xử lý PDF, ảnh, video ở bất kỳ điểm upload nào trong hệ thống |

**Lý do kiến trúc quan trọng:**
- LangChain dùng để trừu tượng hóa Gemini → cho phép đổi LLM provider sau này mà không refactor lớn.
- Azure là non-negotiable cho Pronunciation Assessment — Whisper không có khả năng chấm âm vị, không thể thay thế ở khía cạnh này.
- Whisper chỉ đóng vai trò dự phòng cho STT thuần (lấy transcript, không chấm âm vị) khi Azure STT lỗi/timeout — phạm vi dùng hẹp có chủ đích, tránh nhầm lẫn rằng Whisper thay được vai trò của Azure trong toàn bộ luồng Speaking.
- pgvector nằm trong PostgreSQL để giữ infra tối giản (không thêm vector DB riêng).
- Giới hạn input còn audio + .docx là quyết định thu hẹp phạm vi có chủ đích (trước đó có lúc mô tả rộng hơn là "đa phương thức: văn bản, giọng nói") — áp dụng cho *mọi* điểm tải tài liệu trong hệ thống, không riêng Notebook.

---

## 3. Trạng thái hiện tại

- `de_cuong_khoa_luan.md` đã được viết lại theo cấu trúc mới: 11 mục (trước đó là 12 mục ở một phiên bản cũ hơn), tổ chức feature theo **module kỹ năng** (Module 0–5) thay vì liệt kê phẳng theo Mức 1/2/3. Ba nhãn tier hiện dùng: **Đầy đủ / Thử nghiệm giới hạn / Định hướng mở rộng** — về bản chất tương đương MVP / Experimental / PoC nhưng đây là câu chữ chính thức dùng trong đề cương, cần dùng nhất quán khi viết thêm nội dung.
- Backend scaffold đã có: `core/config.py`, `core/security.py` đã có nội dung; phần lớn file trong `services/` còn trống.
- Phần kiến trúc hệ thống chi tiết và thiết kế dữ liệu (trước đây từng bị lược khỏi một bản nháp đề cương) đã được gộp trở lại vào `de_cuong_khoa_luan.md` ở mục 9 (Kiến trúc hệ thống chi tiết) và mục 10 (Thiết kế dữ liệu), theo quyết định của người dùng — **không tách sang file kỹ thuật riêng**.

### 3.1. Feature: "Rearrange the block" — ĐÃ CHỐT (tier: Thử nghiệm giới hạn)

- **Phạm vi**: chỉ áp dụng cho **Reading và Writing** (Module 1 và Module 3). Loại trừ rõ ràng: Listening, Speaking, Vocabulary.
- **Nguồn nội dung**: ưu tiên lỗi sai trong quá khứ của user (từ `user_errors`); fallback → nội dung bài học có sẵn + Gemini.
- **Chấm điểm**: partial credit theo tỷ lệ vị trí khối (block position ratio).
- **Phân loại lỗi**: hybrid
  - Rule-based diff cho bài tập dạng đóng (closed-form)
  - Gemini structured output, tận dụng (piggyback) trên các lệnh gọi đánh giá Writing đã có sẵn, cho bài tập mở (open-ended)
- **Subsystem**: `error_tracking_service.py`, dùng chung với Adaptive Learning Engine (xem mục 3.4)
  - Bảng: `quiz_attempts`, `user_errors`
  - Enum `error_type` cố định (**giá trị cụ thể chưa chốt — xem mục 4**)
  - Thay thế hoàn toàn bảng `error_log` cũ (generic, đã lỗi thời)

### 3.2. Browser Extension — thiết kế 2 pha (Module 5)

- **Pha 1 (Thử nghiệm giới hạn)**: tra từ trên web (word lookup)
- **Pha 2 (Định hướng mở rộng)**: tra từ trong phụ đề YouTube
- **Auth pattern**: "linking cookie" — **đã thay bằng popup login + `client_type` (quyết định 2026-09-26, mục 3.14)**; thiết kế gốc giữ lại để đối chiếu:
  1. Backend set cookie ngắn hạn, non-httpOnly khi login
  2. Extension đọc cookie qua `chrome.cookies` API
  3. Đổi lấy token pair độc lập qua `POST /api/auth/extension-token`
- **Schema thay đổi**:
  - Thêm `client_type` vào `refresh_tokens`
  - Thêm `source_url` (nullable) vào `vocab_items`
- Tham khảo (không copy): eJOY browser extension & web platform.

### 3.3. Voice Interaction — tách 2 lớp rõ ràng (Module 4)

- **Thử nghiệm giới hạn — Turn-based AI Conversation Partner**: record full audio → STT → LLM (sinh phản hồi + đánh giá ý định/lịch sự + gợi ý slang/cụm thoại trong cùng một lệnh gọi) → TTS → response. Dùng bảng có sẵn `scenarios`, `conversation_turns`.
- **Định hướng mở rộng — Audio transport upgrade only**: WebSocket/WebRTC streaming, VAD endpointing, barge-in handling. **Logic scenario, scoring, context-aware response generation giữ nguyên** — đây chỉ là nâng cấp tầng truyền tải, không phải thay đổi content/NLP logic.
- **Accent vùng miền — ĐÃ LOẠI BỎ HOÀN TOÀN** (quyết định chốt, không phải tạm hoãn): không còn mô phỏng giọng vùng miền (Southern US, British...) ở bất kỳ tier nào. Thay thế bằng **Daily Speaking & Slang cơ bản** — cụm từ giao tiếp hàng ngày và slang có nguồn tham chiếu, tích hợp ngay trong luồng hội thoại turn-based, kèm **Sổ tay Slang/Cụm thoại** (`user_phrasebook_entries`) để người học lưu và ôn tập lại.

### 3.4. Adaptive Learning Engine (Module 0 — ĐÃ NÂNG TIER LÊN "Đầy đủ/MVP")

- Trước đây error-tracking chỉ được mô tả như subsystem hỗ trợ cho Rearrange the block (Thử nghiệm giới hạn). Nay **Adaptive Learning Engine được xác định là module lõi MVP**, bao gồm: nhật ký lỗi, hàng đợi ưu tiên ôn tập, sinh đề kiểm tra động, và (bổ sung mới) theo dõi/mô hình hóa **thói quen học tập** (tần suất học, khung giờ, kỹ năng ưu tiên, tốc độ tiến bộ).
- Hệ quả về schema: `quiz_attempts` và `user_errors` do đó cũng được nâng lên tier Đầy đủ/MVP (không còn ở tier Thử nghiệm giới hạn như trước) — vì đây là hạ tầng lõi engine cần có ngay từ giai đoạn đầu, còn Rearrange the block chỉ là một "người tiêu dùng" thêm của cùng hai bảng này ở tier thấp hơn.

### 3.5. Lộ trình triển khai 20 tuần (mới, mục 8 trong đề cương)

Đã có breakdown theo 8 giai đoạn, thứ tự ưu tiên theo phụ thuộc kỹ thuật: hạ tầng lõi (tuần 1-3) → Đọc/Từ vựng → Viết → Nghe → Adaptive Learning Engine mở rộng → Nói (Conversation Partner + Daily Speaking/Slang) → Rearrange the block → Browser Extension (có thể lược bỏ nếu thiếu thời gian). Movie Delivery Context — nhánh TTS fallback (`movie_context_tts_fallback`) gộp vào cuối Giai đoạn 8 (Thử nghiệm giới hạn, xem mục 3.7); nhánh tìm video thật nằm ngoài lộ trình 20 tuần, thuần định hướng mở rộng.

### 3.6. Viết luận — mở rộng thành 3 nguồn đề bài (Module 3 — ĐÃ CHỐT, tier Đầy đủ giữ nguyên)

- Tính năng trước đây chỉ có 1 loại đề ("Summary Essay" — tóm tắt tài liệu). Nay mở rộng thành **3 nguồn đề bài** người học tự chọn (không ép thứ tự, chỉ là gợi ý mặc định trên UI):
  1. `document_summary` — tóm tắt tài liệu đã học (giữ nguyên thiết kế gốc, chấm theo coverage ý chính từ `document_chunks`).
  2. `extended_topic` — đề luận ý kiến/thảo luận do AI sinh, liên quan đến chủ đề tài liệu đã học nhưng không yêu cầu tóm tắt lại.
  3. `free_topic` — chủ đề tự chọn, hoặc gợi ý đề theo phong cách chứng chỉ quốc tế (TOEIC/IELTS/Cambridge).
- **Quyết định kiến trúc quan trọng**: `extended_topic` và `free_topic` dùng **chung 1 rubric chấm điểm** 4 tiêu chí (Task Response, Coherence & Cohesion, Lexical Resource, Grammatical Range & Accuracy — kiểu IELTS Writing Task 2), **không** xây riêng rubric cho từng chứng chỉ — phong cách chứng chỉ chỉ ảnh hưởng cách sinh đề bài, không ảnh hưởng cách chấm. Quyết định này để kiểm soát scope, tránh phát sinh 3 hệ thống chấm điểm riêng biệt.
- **Schema thay đổi**: `writing_submissions` thêm 3 cột — `source_type` (enum), `prompt_text`, `certificate_style` (nullable). **Bổ sung mục 3.10**: nay có thêm cột `rubric_scores` (JSONB, lưu điểm 4 tiêu chí riêng lẻ) — response API cũng đã cập nhật (mục 3.11).
- **Đây là mở rộng ngoài mô tả gốc trong đề cương/prototype ban đầu** (chỉ có Summary Essay) — đã được cập nhật đồng bộ vào `de_cuong_khoa_luan.md` (mục 3.2, 5.2, mục 9.7 mới, 10.3, 11) và `thiet_ke_database.md` (mục 7 mới).
- **Điểm còn mở, cần xác nhận lại**: ý nghĩa cụ thể của phong cách `cambridge` — hiện hiểu là Cambridge English Writing (FCE/CAE) để nhất quán với việc đây là bài tập viết luận, không phải cấu trúc đề Reading của Cambridge.

### 3.7. Movie Delivery Context — tách 2 tier (Module 5 — ĐÃ CHỐT sau khi rà soát mâu thuẫn giữa các file)

- **Bối cảnh**: `thiet_ke_database.md` từng xếp `movie_context_tts_fallback`/`movie_context_matches` vào Thử nghiệm giới hạn, trong khi `de_cuong_khoa_luan.md`/`lumina_context.md` (bản trước) xếp cả tính năng vào Định hướng mở rộng và loại hẳn khỏi lộ trình 20 tuần — mâu thuẫn logic thật sự (không thể vừa "sẽ implement quy mô nhỏ" vừa "không có trong lịch triển khai nào").
- **Quyết định cuối**: tách rõ 2 tier theo đúng bản chất kỹ thuật:
  - **Nhánh TTS fallback** (`movie_context_tts_fallback`) → **Thử nghiệm giới hạn**. Lý do: tái sử dụng hoàn toàn `llm_service` (sinh câu ví dụ) và `speech_service` TTS (đã bắt buộc xây cho Module 2/4), không phát sinh logic hay tích hợp mới — độ khó triển khai thấp.
  - **Nhánh tìm video thật** (`video_sources`/`video_subtitle_index`) → giữ nguyên **Định hướng mở rộng**, chưa khả thi trong phạm vi khóa luận hiện tại (cần thu thập/index kho video có phụ đề).
- **Lịch trình**: nhánh TTS fallback gộp vào cuối Giai đoạn 8 (tuần 19-20) trong `de_cuong_khoa_luan.md` mục 8, sau khi `speech_service` đã sẵn sàng từ Giai đoạn 4.
- **Rủi ro cần chuẩn bị khi bảo vệ khóa luận**: nếu chỉ có nhánh TTS fallback (chưa có video thật), giá trị khác biệt so với các chức năng sinh câu ví dụ + TTS đã có ở module khác (Vocab lookup, Podcast) là hạn chế — cần định vị rõ đây là bước đệm hạ tầng cho nhánh video thật sau này, không phải sản phẩm hoàn chỉnh độc lập.
- **Quyết định của người dùng**: giữ nhánh TTS fallback vì vẫn muốn hướng tới nhánh video thật sau này; nếu về sau không triển khai được trong thời gian còn lại, sẽ bỏ nhánh TTS fallback (không lùi về Định hướng mở rộng một mình nó — bỏ nghĩa là bỏ hẳn khỏi lộ trình, không giữ ở tier trung gian).
- **Bổ sung mục 3.10**: đã tạo sẵn bảng `video_sources`/`video_subtitle_index` trong `schema.sql` (chưa implement logic) để `movie_context_matches.source_type = 'real_video'` có FK hợp lệ ngay từ đầu.

### 3.8. STT fallback cho Speaking — Azure ưu tiên, Whisper dự phòng (Module 4 — ĐÃ CHỐT)

- **Bối cảnh**: `de_cuong_khoa_luan.md` mục 5.1 (bản trước) nhắc "Whisper" như thể là công cụ STT chính, mâu thuẫn với phần kiến trúc chi tiết (mục 9.2/9.4/9.6 cùng file) và bảng tech stack — vốn đều chốt Azure Speech là bắt buộc. Khi rà soát lại, phát hiện đây là câu chữ sai sót (chưa đồng bộ), không phải 1 quyết định kiến trúc thật.
- **Quyết định cuối, sau khi cân nhắc lại**: thay vì chỉ sửa câu chữ cho khớp Azure, quyết định biến "Whisper" thành **STT dự phòng có chủ đích** — bổ sung giá trị thực (tăng tính sẵn sàng của luồng hội thoại) thay vì xoá hẳn:
  - **Nhánh A (STT thuần, lấy transcript cho LLM)**: Azure STT ưu tiên → lỗi/timeout, retry 1 lần → vẫn lỗi → fallback sang Whisper (OpenAI Whisper API).
  - **Nhánh B (Azure Pronunciation Assessment)**: **không có fallback** — Whisper không có khả năng chấm âm vị, đây vẫn là lý do "Azure non-negotiable" ban đầu, chỉ áp dụng đúng cho nhánh B, không áp dụng cho nhánh A.
- **Lý do cân nhắc trước khi chốt**: ban đầu đề xuất phương án đơn giản hơn (nhánh A lỗi thì trả lỗi rõ ràng, không cần provider thứ 2) để tránh phát sinh dependency mới không cần thiết (đúng tinh thần scope discipline). Người dùng chọn xây fallback thật sự vì ưu tiên tính sẵn sàng của luồng hội thoại — chấp nhận thêm 1 dependency (OpenAI Whisper API), phạm vi dùng giới hạn nghiêm ngặt (chỉ STT dự phòng nhánh A, không dùng cho mục đích nào khác).
- **Schema thay đổi**: `conversation_turns` thêm cột `stt_provider_used` (enum `'azure'`/`'whisper'`) để theo dõi tần suất fallback thực tế — có thể dùng làm số liệu minh hoạ tính resilience khi bảo vệ khóa luận.
- Chi tiết flow/business rules xem `docs/feature-speaking.md` mục 1.3-1.6; đối chiếu đề cương xem `de_cuong_khoa_luan.md` mục 9.4.

### 3.9. Rà soát đối chiếu DB lần 3 (phân tích chéo toàn bộ 10 file .md của project) — 2 điểm ĐÃ CHỐT + danh sách điểm mở

> Bối cảnh: rà soát toàn diện theo yêu cầu người dùng, đối chiếu `thiet_ke_database.md` với `de_cuong_khoa_luan.md`, 4 file `feature-*.md`, `api-spec.md`, `test-cases (1).md`.

**Quyết định 1 — `reading_answers` thiếu cột trích dẫn cho Skim & Scan:**
- Bản sửa mục 5 (rà soát lần 2, đã có trong `thiet_ke_database.md`) đã cho `reading_sessions.document_id` nullable + thêm `generated_passage_id`, nhưng **chưa sửa `reading_answers`** — cột `source_chunk_id` ở đó vốn chỉ có nghĩa khi trích dẫn từ `document_chunks` (dùng cho Classic Mode). Skim & Scan trích dẫn theo vị trí trong `generated_passages.content` (offset/chunk nội bộ), không qua `document_chunks` (đúng như `feature-reading.md` mục 2.3 mô tả) — nghĩa là hiện tại `reading_answers` không có chỗ lưu trích dẫn hợp lệ cho các session Skim & Scan.
- **Quyết định**: thêm 1 cột mới (nullable) trên `reading_answers` dành riêng cho trích dẫn Skim & Scan (lưu offset/tham chiếu vị trí trong `generated_passages.content`); `source_chunk_id` chuyển thành nullable, chỉ set khi session liên quan có `mode = 'classic'`.
- **Đã hoàn tất** (mục 3.10): cột `passage_citation_ref` đã có trong `thiet_ke_database.md` mục 9.1 và `docs/schema.sql`. **Đính chính 2026-09-24**: cột này chưa bao giờ có trong DB thật và Skim & Scan chưa sinh trích dẫn — đã gỡ khỏi `docs/schema.sql`/ERD, xem `thiet_ke_database.md` mục 12.

**Quyết định 2 — Quan hệ `quizzes` ↔ `quiz_attempts`:**
- Trước rà soát này, `quizzes` xuất hiện trong danh sách bảng MVP (mục 2, mục 10.2 đề cương) nhưng không có mô tả cấu trúc/quan hệ ở bất kỳ đâu trong 10 file. Bằng chứng gián tiếp từ `api-spec.md`: `POST /api/adaptive/quizzes/generate` trả về `quiz_id` + `questions`, trong khi `POST /api/reading/rearrange` và `POST /api/writing/rearrange` chỉ trả `attempt_id` + `blocks`, không có `quiz_id` nào — cho thấy Rearrange chưa từng được thiết kế để đi qua một "bộ đề" (`quizzes`) trung gian.
- **Quyết định**: `quizzes` chỉ dành riêng cho đề kiểm tra động do Adaptive Learning Engine sinh (qua `/api/adaptive/quizzes/generate`). Rearrange the Block **không** tạo dòng `quizzes` — tiếp tục ghi thẳng vào `quiz_attempts` như thiết kế đã có, với `quiz_id = NULL`. Quan hệ `quizzes` ↔ `quiz_attempts` là **1-nhiều**: `quiz_attempts.quiz_id` là FK nullable trỏ tới `quizzes`, chỉ set khi lượt làm bài thuộc 1 bộ đề đã sinh qua Adaptive Engine.
- **Đã hoàn tất** (mục 3.10): bảng `quizzes` + cột `quiz_attempts.quiz_id` đã có trong `thiet_ke_database.md` mục 9.2 và `docs/schema.sql`.

### 3.10. `schema.sql` lần đầu tiên + xử lý toàn bộ 8 điểm mở của rà soát lần 3 (ĐÃ CHỐT)

- Đã sinh `docs/schema.sql` (PostgreSQL 16 + pgvector) — bản DDL đầy đủ đầu tiên của project, phản ánh toàn bộ `thiet_ke_database.md` mục 1-9 và `erd_1.mermaid`. **Đã test chạy thật**: tạo database sạch trên PostgreSQL 16 + pgvector 0.6.0, áp toàn bộ DDL không lỗi, chạy functional test cho CHECK constraint (`writing_submissions`, `reading_sessions`), `ON DELETE CASCADE` (xoá `documents` kéo theo xoá đúng `writing_submissions` phụ thuộc), trigger tự động ghi `user_errors`, và truy vấn similarity qua index HNSW trên `document_chunks.embedding` — không chỉ đọc qua bằng mắt.
- 3 quyết định mới chốt trong lần này:
  1. **`writing_coherence` (điểm mở #9)** — chọn phương án thêm flow tự động. Thêm cột `writing_submissions.rubric_scores` (JSONB, 4 tiêu chí thang 0-100: `task_response`, `coherence_cohesion`, `lexical_resource`, `grammatical_range_accuracy`; chỉ áp dụng `extended_topic`/`free_topic`, NULL với `document_summary`). Trigger `trg_writing_submissions_flag_coherence`: khi bài vừa chấm xong (`completed_at` chuyển từ NULL sang có giá trị) và `coherence_cohesion < 60`, tự động ghi 1 `user_errors(error_type='writing_coherence')` — cùng nguyên tắc "piggyback, không tốn thêm lệnh gọi LLM" như Inline Grammar Correction đang làm với `grammar`. **Ngưỡng 60/100 là đề xuất** (mượn cách phân dải điểm đã dùng cho `intent_score`/`politeness_score` ở Speaking) — cần xác nhận lại như các đề xuất rubric khác, xem mục 4 điểm 1.
  2. **Phạm vi token Extension (điểm mở #13)** — chốt: token `client_type='extension'` chỉ được gọi `/api/extension/*` + `/api/reading/lookup` + `/api/vocab`, không gọi được các route web khác. Đây là chính sách tĩnh, không cần thêm cột DB — `refresh_tokens.client_type` đã đủ để middleware xác định. **TODO code (không phải điểm mở thiết kế nữa)**: viết middleware kiểm tra `client_type` theo allow-list route cố định trước khi code Extension thật — xem mục 4 điểm 4.
  3. **`test-cases (1).md` (điểm mở #14)** — xác nhận đây là bản chính thức duy nhất, hậu tố "(1)" không phải dấu hiệu mất bản gốc nào khác. Không cần hành động thêm.
- Điểm mở #10 (ON DELETE), #11 (chính sách CHECK constraint), #12 (`movie_context_matches.source_type='real_video'` phụ thuộc tier chưa build), #8 (đồng bộ ERD/schema), #15 (thiếu file `schema.sql`/`erd.mermaid`) — xử lý trực tiếp trong `docs/schema.sql`:
  - **ON DELETE**: chính sách nhất quán theo 4 nguyên tắc — (a) CASCADE từ `users` (hỗ trợ xoá tài khoản); (b) CASCADE cho quan hệ tham gia CHECK dạng XOR bắt buộc-1-trong-2 (để tránh vi phạm CHECK nếu chỉ SET NULL một vế — vd `reading_sessions`, `reading_answers`, `vocab_items`, `writing_submissions`, `movie_context_matches`); (c) RESTRICT cho bảng thư viện dùng chung khi cột NOT NULL (`scenarios`, `personas` trong vài trường hợp — bảo vệ lịch sử người dùng khỏi bị xoá theo khi ai đó sửa thư viện nội dung); (d) SET NULL cho tham chiếu optional thuần túy (persona lựa chọn, `quiz_id`, `slang_phrase_id`...). Chi tiết đầy đủ ở đầu file `schema.sql`.
  - **CHECK constraint**: `writing_submissions` nay có `CHECK` ở DB cho ràng buộc `document_id` theo `source_type` (trước đó chỉ validate tầng service, theo `thiet_ke_database.md` mục 7) — nhất quán với `reading_sessions`/`vocab_items`/`reading_answers`. Chính sách này không còn "thiếu nhất quán" nữa.
  - **`movie_context_matches`**: tạo sẵn `video_sources`/`video_subtitle_index` (tier Định hướng mở rộng, CHƯA implement logic tìm video) ngay trong `schema.sql`, để `source_type = 'real_video'` có FK hợp lệ từ đầu, không cần ALTER thêm khi làm nhánh video thật sau này.
  - **Đồng bộ ERD/schema**: `schema.sql` đã phản ánh đầy đủ 2 quyết định mục 3.9 (`reading_answers.passage_citation_ref`, `quiz_attempts.quiz_id`).
- **Không thuộc phạm vi rà soát lần 3, vẫn còn mở nguyên trong mục 4**: giá trị chính thức của enum `error_type` (điểm 1 — `writing_coherence` nay có flow cụ thể nhưng bản thân enum 9 giá trị vẫn cần xác nhận chính thức), seed data `slang_phrases` (điểm 2), tên đề tài (điểm 3), logic điểm ý định/lịch sự (điểm 6), nghĩa `cambridge` (điểm 7).

Chi tiết SQL cụ thể và log test xem trực tiếp `docs/schema.sql` (phần comment đầu file + cuối file).

### 3.11. Đồng bộ hoá `api-spec.md`/`test-cases (1).md`/`erd.mermaid` với `schema.sql` (rà soát lần 4, do người dùng chủ động hỏi)

> Bối cảnh: sau khi sinh `docs/schema.sql` (mục 3.10), người dùng hỏi thẳng "các file mới cung cấp đã thống nhất với các file cũ chưa xử lý chưa?" — phát hiện `docs/schema.sql` và `erd_1.mermaid` **đã** được đồng bộ ngay khi tạo (mục 3.10), nhưng 2 tài liệu triển khai/kiểm thử (`api-spec.md`, `test-cases (1).md`) thì **chưa** — chúng vẫn mô tả các điểm mở như thể chưa được quyết định, dù `schema.sql` đã chốt logic. Đây là khoảng hở tài liệu thật, không phải hiểu lầm của người dùng.

- **Về việc có "2 file `schema.sql`"**: xác nhận chỉ có **1 nội dung duy nhất**, tồn tại ở 2 nơi có mục đích khác nhau — bản tải xuống gửi thẳng vào hội thoại (để tải về máy) và `docs/schema.sql` lưu trong project (để các phiên làm việc sau đọc lại) — đã diff nhị phân, khớp 100% (37.415 byte cả hai). Không có version lệch nhau.
- **2 khoảng hở tài liệu tìm thấy và đã xử lý**:
  1. **Phạm vi token Extension** (quyết định mục 3.10 điểm 2) chưa từng được ghi vào `api-spec.md` (mục 0.2 Auth, mục 8 Module 5) hay `test-cases (1).md` (`AUTH-007`) — `AUTH-007` vẫn ghi "cần xác nhận business rule... điểm cần làm rõ với đội dự án" dù quyết định đã chốt từ mục 3.10. **Đã sửa**: `api-spec.md` mục 0.2 + mục 8 nay ghi rõ allow-list + TODO middleware; `AUTH-007` đổi từ EC sang BR với kết quả mong đợi cụ thể (`HTTP 403`, `error_code: extension_token_scope_denied`), thêm `AUTH-007b` xác nhận 2 route được phép vẫn hoạt động bình thường.
  2. **`rubric_scores`** (cột mới thêm khi viết `schema.sql`, mục 3.10 điểm 1) chưa xuất hiện trong response `POST /api/writing/submissions/{id}/submit` ở `api-spec.md` mục 5. **Đã sửa**: thêm field `rubric_scores` vào response, kèm giải thích khi nào có giá trị/khi nào NULL; thêm `WR-012b` ở `test-cases (1).md` kiểm tra đúng ràng buộc này.
- `api-spec.md` Phụ lục A (enum `error_type`) và Phụ lục B (lịch sử đối chiếu ERD) cũng được cập nhật: Phụ lục A ghi chú `writing_coherence` nay có flow ghi dữ liệu cụ thể; Phụ lục B thêm 2 mục mới (5, 6) cho `rubric_scores` và phạm vi token Extension, theo đúng format nhật ký đối chiếu đã có sẵn ở đó.
- **Đã rà soát, xác nhận KHÔNG có mâu thuẫn** (không cần sửa) ở các file còn lại: `feature-writing.md` (mô tả rubric 4 tiêu chí khớp 100% với `rubric_scores`/trigger trong `schema.sql`), `de_cuong_khoa_luan.md` mục 11 (danh sách điểm mở của đề cương không mâu thuẫn — các điểm liệt kê ở đó là điểm 1/7 trong mục 4 hiện tại, vẫn đang mở đúng như đề cương ghi, không bị `schema.sql` "âm thầm chốt" mà quên cập nhật đề cương), `feature-reading.md`/`feature-listening.md`/`feature-speaking.md` (không có phần nào mô tả cấu trúc DB mâu thuẫn với `schema.sql`).
- **Bài học quy trình**: từ nay, mỗi lần một quyết định được chốt trực tiếp trong `schema.sql`/`erd.mermaid` (thay vì trong file `.md` mô tả trước), cần chủ động rà lại `api-spec.md` và `test-cases (1).md` xem có chỗ nào đang mô tả điểm đó như "chưa quyết định" hay không — bổ sung vào nguyên tắc làm việc ở mục 5.

### 3.12. Bắt đầu implementation thật + 2 tính năng mới: RAG Chat (Notebook) và Skim & Scan gắn tài liệu thật (2026-09-16)

> Bối cảnh: khác các mục 3.1-3.11 (thuần quyết định thiết kế/tài liệu), đây là lần đầu **code thật chạy được** trên Postgres + Gemini thật, không chỉ cập nhật `.md`. Backend scaffold trước đó gần như trống (`lumina_context.md` mục 3 cũ); phiên này implement đủ Auth, Notebook (CRUD + ingestion), Reading Classic + Skim & Scan, Vocab (SM-2), Writing (3 nguồn đề), và 2 tính năng mới theo yêu cầu trực tiếp của người dùng.

- **Document Ingestion Pipeline** (mới, prerequisite cho cả 2 tính năng dưới) — `.docx` được extract + chunk (~350 từ/chunk) + embed (Gemini `models/gemini-embedding-001`, 768 chiều) **ngay đồng bộ lúc upload**, không cần polling `processing` như thiết kế gốc giả định. Audio chưa có pipeline thật (cần `AZURE_SPEECH_KEY`, hiện là placeholder) — vẫn dừng ở `processing`, đúng phạm vi Module Listening chưa build. Chi tiết: `feature-notebook.md` mục 1.
- **RAG Chat kiểu NotebookLM** (tính năng mới, theo yêu cầu người dùng) — hỏi đáp tự do trên 1 tài liệu đã upload, trả lời chỉ dựa vào `document_chunks` liên quan nhất (pgvector cosine search) + Gemini, kèm trích dẫn nguồn. Bảng mới `notebook_chat_messages`. Chi tiết: `feature-notebook.md` mục 2.
- **Skim & Scan gắn tài liệu thật** (thay đổi hành vi, theo yêu cầu người dùng) — trước đây passage **luôn** do AI tự sinh (mục 5 `thiet_ke_database.md`, dựa theo `server.ts` prototype). Nay thêm nhánh `document_id`: passage là 1 chunk **nguyên văn** từ tài liệu user (không AI paraphrase), `generated_passages.source_document_id` lưu lại nguồn. Câu hỏi trắc nghiệm vẫn luôn do AI sinh ở cả 2 nhánh. Chi tiết: `feature-reading.md` mục 2 (đã viết lại).
- **Bug thật phát hiện và sửa trong lúc implement** (không phải yêu cầu ban đầu, phát sinh khi test thật với Gemini quota hết giữa phiên):
  - `llm_service.py` trước đó không bắt exception khi Gemini lỗi (quota/network) → FastAPI trả lỗi 500 không có CORS header → browser hiển thị "Failed to fetch" thay vì thông báo có ý nghĩa. Đã thêm `AIServiceError` + wrapper `_call_gemini` tại **một điểm duy nhất**, mọi service (Writing, Reading, Notebook Chat) giờ trả `503 ai_service_unavailable` nhất quán khi Gemini lỗi — verify được bằng cách test thật khi quota free-tier hết (không phải giả lập).
  - `reading_service.py` có `lookup_term` định nghĩa trùng 2 lần (dead code từ trước) — đã dọn.
- **Rủi ro vận hành quan trọng cho ngày bảo vệ khóa luận**: Gemini free-tier chỉ cho **20 request `generate_content`/ngày/model** — bị exhaust nhiều lần ngay trong phiên implement này (từ test lặp lại). Notebook Chat, Skim & Scan (câu hỏi), và Writing đều phụ thuộc quota này. Cần nâng cấp gói trả phí Gemini trước khi demo trực tiếp, hoặc chấp nhận rủi ro gặp `503` giữa buổi bảo vệ.
- **Khoảng hở tài liệu-vs-code phát hiện được (có sẵn từ trước, không phải lỗi phiên này)**: tech stack ở mục 2 file này ghi "LangChain dùng để trừu tượng hóa Gemini", nhưng `llm_service.py`/`rag_service.py` gọi thẳng `google-generativeai`, không qua LangChain ở đâu cả — xem `thiet_ke_database.md` mục 11 để biết chi tiết và 2 hướng xử lý đề xuất. **Cần người dùng xác nhận hướng đi** trước khi viết thêm code LLM mới, để tránh lệch tiếp.
- **Việc cố ý chưa làm trong phiên này** (out of scope, cần phase riêng): `POST /api/writing/prompts/suggest` (gợi ý 2-3 đề free_topic theo certificate_style), `/api/writing/grammar-check`, `/api/writing/rephrase`, `/api/writing/rearrange`, Gamification, Listening, Speaking — vẫn là file service rỗng.

### 3.13. Module 2 — Listening: Dictation implement + test thật, Podcast/Transcript vẫn chờ key (2026-09-17)

> Bối cảnh: theo lộ trình 20 tuần (mục 3.5), Nghe (Listening) là module kế tiếp sau Viết. Trong 3 tính năng của `feature-listening.md` (Podcast, Transcript đồng bộ, Dictation), chỉ **Dictation** implement được ngay — Podcast/Transcript cần ElevenLabs (TTS) + Azure Speech (STT) thật, cả 2 đều chưa có key (`AZURE_SPEECH_KEY` vẫn là placeholder; `ELEVENLABS_API_KEY` trước đây chưa từng tồn tại trong project, nay đã thêm chỗ trong `Settings`/`.env.example` nhưng vẫn rỗng). Người dùng xác nhận hướng đi: build Dictation trước (không cần key), việc còn lại (mục 4 điểm 9 cũ) vẫn mở.

- **Phát hiện quan trọng, chưa từng ghi nhận trước đây**: `docker-compose.yml` mount `./schema.sql` (schema gốc ở root project, bản prototype cũ — `uuid_generate_v4()`, không có `error_type_enum`/`user_errors`) vào `docker-entrypoint-initdb.d`, **KHÔNG PHẢI** `docs/schema.sql` (bản thiết kế đầy đủ, đã test riêng trên DB sạch ở mục 3.10). Volume Postgres thật (`postgres_data`, chưa từng bị xoá từ đầu dự án) được khởi tạo từ schema gốc này, rồi được Alembic patch dần lên qua từng migration (đúng cách `writing_submissions` đã được mở rộng ở mục 3.12) — **`docs/schema.sql` là tài liệu thiết kế mục tiêu, không phải ảnh chụp schema đang chạy thật**. Đã xác nhận trực tiếp qua `\d` trên `lumina_db`: `podcasts`/`personas`/`transcript_segments`/`dictation_attempts` đã tồn tại sẵn (rỗng) nhưng với tên cột khác `docs/schema.sql` (`script_text`, `word_index`/`word_text`/`start_time_ms`/`end_time_ms`, `persona_ids[]` thay vì `persona_id`...); `user_errors` **chưa tồn tại**, DB vẫn còn bảng `error_log` cũ. **Cần ghi nhớ cho mọi phiên implement sau**: trước khi viết model mới cho 1 bảng "đã có trong schema.sql", luôn kiểm tra bằng `docker exec lumina_db psql ... -c "\d <table>"` trước, không giả định `docs/schema.sql` khớp DB thật.
- **Migration `20260917_0008`**: mở rộng (không thay bảng mới) `personas` (+`is_active`, `+created_at`), `podcasts` (+`persona_id` số ít thay `persona_ids[]` cũ — đã DROP cột cũ vì bảng rỗng, +`status`), `dictation_attempts` (+`start_word_index`/`end_word_index`/`audio_segment_path`/`reference_word_tags`); và tạo mới `user_errors` (đúng quyết định mục 3.1 thay `error_log`) — CHECK constraint theo 9 giá trị `error_type` đề xuất (vẫn "chưa chốt chính thức" như mục 4 điểm 1 ghi, chỉ dùng tạm để enforce ở DB).
- **`app/models/adaptive.py` (mới)**: model tối thiểu `UserError` — **KHÔNG khai báo `ForeignKey` tới `quiz_attempts`** ở tầng SQLAlchemy dù cột `quiz_attempt_id` có FK thật ở DB, vì chưa có model `QuizAttempt` nào đăng ký vào `Base.metadata` (test thật phát hiện lỗi `NoReferencedTableError` khi flush — SQLAlchemy cần resolve được bảng đích trong cùng metadata để sort dependency lúc commit). Sẽ cần sửa lại khi Adaptive Learning Engine build model `QuizAttempt` thật.
- **`app/services/speech_service.py` (mới)** — điểm gọi STT/TTS duy nhất theo đúng nguyên tắc mục 4 `feature-listening.md`: `slice_wav_segment()` cắt audio PCM WAV thật bằng module `wave` chuẩn (không cần ffmpeg, chỉ hỗ trợ WAV — khớp chuẩn hoá bắt buộc "PCM WAV 16kHz mono" trước Azure Speech SDK), đã test bằng file WAV thật (không giả lập). `synthesize_speech()`/`transcribe_audio()` raise `SpeechServiceError` rõ ràng ngay (503) vì chưa có key — cùng pattern `AIServiceError` của `llm_service.py`.
- **Dictation (`app/services/listening_service.py` + `app/utils/dictation_grading.py` + `app/utils/word_frequency.py`)**: implement đầy đủ business rule mục 3.3-3.5 — diff cấp từ bằng `difflib` (stdlib), khoảng cách ngữ âm bằng Metaphone (`jellyfish`, khoảng cách ≤1 ký tự trên mã Metaphone coi là "gần"), gắn nhãn từ hiếm bằng tần suất Zipf (`wordfreq`, ngưỡng 3.3 ≈ top 5.000-8.000 từ thông dụng — hiệu chỉnh thủ công, ghi rõ trong code), gắn nhãn tên riêng bằng heuristic viết hoa-không-ở-đầu-câu. Có 2 đơn giản hoá có chủ đích, ghi rõ trong code (không phải lỗi che giấu): (1) lỗi "extra" (từ thừa người học gõ) không ghi vào `user_errors` — không có từ gốc để so khớp ngữ âm/độ hiếm; (2) lỗi "missing" (từ bị bỏ trống hoàn toàn) không tính khoảng cách ngữ âm được (không có gì để so) — phân loại thuần theo độ hiếm của từ bị bỏ sót, không phải quy tắc gốc trong spec.
- **Test thật, không mock**: 18 unit test (`tests/test_dictation_grading.py`, hàm thuần, không DB) + 10 integration test (`tests/test_listening_dictation_integration.py`, API thật qua `TestClient` + Postgres Docker thật + 1 file WAV thật tự sinh bằng module `wave` — không audio thật có nội dung nghe được, nhưng file nhị phân thật, `slice_wav_segment` cắt thật, không giả lập). Cả 28 test PASS. Dictation không gọi Gemini nên **không bị ảnh hưởng bởi giới hạn quota** (khác Writing/Reading/Notebook Chat) — chạy toàn bộ suite còn lại (`pytest --ignore=tests/test_writing_integration.py`) cho 52/55 pass, 3 fail còn lại đều là `503 ai_service_unavailable` do hết quota Gemini ngày hôm đó (`test_notebook_chat_integration`, `test_reading_skim_scan_integration` x2) — xác nhận không phải regression từ thay đổi lần này.
- **Cố ý CHƯA làm trong phiên này** (out of scope, chờ key hoặc phase riêng): endpoint tạo Podcast thật (`POST /api/listening/podcasts`) và Transcript (`GET .../transcript`) — cả 2 cần `speech_service.synthesize_speech`/`transcribe_audio` thật; kết nối `frontend-reference/src/components/ListeningView.tsx` — chưa nối vì chưa có UI/luồng Podcast thật để demo Dictation cho người dùng (Dictation cần 1 podcast `status=ready` có sẵn, hiện chỉ tạo được qua seed test hoặc thao tác DB trực tiếp); Adaptive Learning Engine đầy đủ (router/schema/`GET /api/adaptive/*`) — chỉ mới có bảng `user_errors` được ghi vào, chưa có endpoint đọc lại.

### 3.14. Trạng thái code thực tế 2026-09-25 + Movie Context (TTS fallback) + middleware token Extension

> Bối cảnh: mục 3.13 dừng ở 2026-09-17; từ đó code đã đi xa hơn tài liệu. Danh sách dưới đây lấy từ đối chiếu trực tiếp cây mã nguồn (router/service/migration/test), **không phải** từ một lần chạy test toàn bộ.

- **Đã có code** (ngoài những gì mục 3.12-3.13 ghi): Adaptive Learning Engine (`adaptive_service`, `priority_queue_service`, router `/api/adaptive`, model `QuizAttempt`/`UserError`), Rearrange the Block (Reading + Writing), Podcast + Transcript (Azure TTS/STT chạy được — mục 4 điểm 10 cũ không còn chặn), Speaking turn-based + slang/phrasebook + STT dự phòng, Notebook audio, Gamification (streak/XP/skill progress), `/api/users/me`, Vocab practice/stories, Browser Extension (`extension/`, tra từ + lưu từ). Migration mới nhất trước phiên này: `20260924_0016`.
- **Movie Delivery Context — nhánh TTS fallback (MỚI, 2026-09-25)**: `GET /api/movie-context/search`, `POST .../matches/{id}/save`, `GET .../matches/{id}/audio`. Sinh 3 câu thoại bằng `llm_service.generate_movie_example_sentences`, đọc mẫu bằng TTS (tái dùng `podcast_service._synthesize`, giọng theo `personas`), cache dùng chung ở `movie_context_tts_fallback` theo (câu, persona) — tra bằng `IS NOT DISTINCT FROM` vì unique constraint không chặn được persona NULL. Từ 2026-09-26 có thêm bước tìm phụ đề trong kho video demo (xem bullet "kho video demo" bên dưới). Không cần migration (bảng có sẵn). **Frontend đã nối** (`frontend-reference/src/components/MovieContextPanel.tsx`, thay mock Express trong tab Movie Context của `ListeningView`; `tsc --noEmit` sạch + `vite build` thành công, **chưa thử tay trên trình duyệt** vì backend/DB chưa chạy; UI ghi rõ đây là câu thoại AI đọc mẫu, không phải clip phim thật; `VideoPlayerOverlay.tsx` được viết lại phát video thật, type `MovieMatch` đã xoá — xem bullet kho video demo). Test: `tests/test_movie_context_integration.py` (LLM/TTS giả, DB thật) — **4/4 pass với Postgres thật (2026-09-26)**.
- **Middleware phạm vi token Extension (MỚI — đóng TODO mục 4 điểm 4 cũ)**: `app/core/extension_scope.py`, gắn trong `main.py` *trước* CORS (để 403 vẫn có CORS header). Đọc claim `client_type` trong JWT; token `extension` chỉ qua được `/api/extension/*`, `/api/reading/lookup`, đúng `/api/vocab` (không gồm `/api/vocab/*`); còn lại `403 {"detail": {"error_code": "extension_token_scope_denied"}}`. Token cũ không có claim = `web`. `LoginRequest` có thêm `client_type` (`web` mặc định | `extension`) — tự khai là an toàn vì chỉ *thu hẹp* quyền; `rotate_refresh_token` giữ nguyên loại client nên refresh không "nâng cấp" token extension. `extension/background.js` đã gửi `client_type: "extension"` khi login. `tests/test_extension_scope.py`: 14/14 pass với Postgres thật (2026-09-26), gồm login/refresh giữ scope và route `/api/extension/lookup`.
- **Migration `20260925_0017` (thêm `refresh_tokens.client_type` + CHECK) ĐÃ ÁP 2026-09-26** (người dùng cho phép; sao lưu `pg_dump -Fc` trước khi áp; 1.367 refresh token cũ mặc định `web`). `schema.sql` gốc đã sinh lại bằng `pg_dump`, diff so với bản cũ chỉ là cột `client_type` + CHECK.
- **`POST /api/extension/lookup` (EXT-002) — ĐÃ CÓ (2026-09-26, `routers/extension.py`)**: dùng lại đúng handler tra từ của Reading (Ollama, nghĩa theo ngữ cảnh câu) để tra từ trên mọi trang web; `extension/background.js` gọi route này. Kiểm tra thật với Ollama: cùng từ "bank" ra "bờ (sông, hồ)" với câu picnic và "ngân hàng" với câu gửi séc (đăng nhập bằng token extension, mất 40-50 giây khi model chưa nạp).
- **QUYẾT ĐỊNH 2026-09-26 — Xác thực extension = popup login + `client_type`, KHÔNG build "linking cookie"** (`POST /api/auth/extension-token`, EXT-001/EXT-004, AUTH-006 đánh dấu không build). Lý do: tra nghĩa theo ngữ cảnh gọi Ollama nên bắt buộc có token; cả 2 cách đều cho token, nhưng linking cookie thêm 1 cookie không-httpOnly mà mọi script cùng origin đều đọc được (mở rộng bề mặt tấn công), trong khi popup login không có bí mật nào đọc được ngoài token đã bị giới hạn phạm vi route (mục trên). Đổi lại người dùng gõ mật khẩu 1 lần trong popup. Thiết kế gốc vẫn ghi ở mục 3.2 và `de_cuong_khoa_luan.md` để đối chiếu.
- **Movie Context — kho video demo (MỚI, 2026-09-26)**: 3 cảnh hội thoại MÔ PHỎNG (`storage/videos/demo_*.mp4`, 150-200 KB) do `scripts/seed_demo_videos.py` dựng (giọng Azure TTS 2 người + khung hình có phụ đề, ghi rõ "SIMULATED DEMO SCENE"; ffmpeg lấy từ gói `imageio-ffmpeg`, không nằm trong requirements) — không tải phim thật vì không có phim tự do bản quyền nào chứa đúng các idiom cần demo. Idiom có trong kho: "piece of cake", "break the ice", "under the weather". `GET /api/movie-context/search` giờ **tìm phụ đề trước** (full-text Postgres cấu hình `simple` trên `video_subtitle_index` — `english` bỏ stopword nên "hang out"/"you can say that again" khớp lỏng, đã tái hiện và sửa) rồi mới rơi về TTS fallback. Match `real_video` có `video_url`/`title`/`start_ms`/`end_ms`; `GET .../matches/{id}/video` kiểm tra sở hữu + chặn path traversal. Frontend: `VideoPlayerOverlay.tsx` viết lại phát `<video>` thật (nhảy tới trước dòng khớp 2,5 giây), type `MovieMatch` đã xoá. Test: `test_video_match_preferred_over_tts_and_served`, `test_no_video_match_falls_back_to_tts`. Đây là **bước tiến nhỏ của nhánh `real_video` (mục 3.7) cho mục đích demo**, không phải kho video thật — thu thập/đánh chỉ mục video thật vẫn là Định hướng mở rộng. Chạy lại seed: `PYTHONUTF8=1 python scripts/seed_demo_videos.py [--force]` từ thư mục `backend`. **Video thật**: `scripts/ingest_video.py --video <file> --srt <file.srt> --title "..." [--start --end]` (nén 480p, cắt đoạn, gộp cue thành câu qua `app/utils/subtitles.py`, in idiom có trong đoạn để chọn cụm demo; test `tests/test_subtitles.py`; đã chạy thử đường ống bằng dữ liệu giả rồi dọn). Do video nằm sau JWT nên trình duyệt tải nguyên file → cắt đoạn ≤ ~15 phút/phim. **Đã nạp phim thật đầu tiên (2026-09-26): "Tears of Steel"** (Blender Foundation, CC BY 3.0; video 720p + `TOS-en.srt` chính thức từ mango.blender.org/download; nén 480p còn 65 MB, 75 câu đã đánh chỉ mục, `platform='film'`). Đã kiểm tra khớp giờ phụ đề–tiếng bằng Azure STT trên đoạn 22–32 giây (lệch ~0,3 giây) và gọi API thật trên container `lumina_api` (cần `docker compose restart api` mỗi khi đổi code vì compose không bật `--reload`). Cụm demo có trong phim: "freaked out", "all systems go", "speed it up". Overlay hiển thị dòng ghi công CC BY (bảng `FILM_CREDITS` trong `VideoPlayerOverlay.tsx`, phải thêm mục mới khi nạp phim khác). Phim ít idiom truyền thống (chủ yếu khẩu ngữ); His Girl Friday (public domain, nhiều idiom hơn) chưa nạp vì cần file `.srt` khớp bản phim. Charade đã loại (link Internet Archive 404 + bản quyền tranh cãi).

- **Phim thật thứ 2 + phụ đề chạy theo thoại (2026-09-27)**: nạp "The Little Shop of Horrors" (1960, public domain — Wikimedia Commons; phụ đề tiếng Anh do người viết từ TimedText của Commons; đoạn 48:00–60:00, 26,7 MB, 252 câu; cụm demo: "keep an eye on", "take care of", "figure out", "shut up", "come on"). Giờ phụ đề khớp tiếng, kiểm bằng Azure STT (lệch < 1 giây). Endpoint mới `GET /api/movie-context/matches/{id}/subtitles`; `VideoPlayerOverlay` hiện phụ đề theo thời gian phát cho phim thật (cảnh `demo` đã ghi cứng phụ đề vào hình nên bỏ qua): dòng chứa cụm đã tìm màu hổ phách, dòng thoại khác màu trắng. Test mở rộng ở `test_movie_context_integration` (10/10 pass với `test_subtitles`), API đã restart. `ingest_video.py` nhận được URL nhưng tua qua HTTP không chạy với webm của Commons (không có index) — script giờ báo lỗi khi ffmpeg ra file rỗng; nên tải phim về trước. Chưa xem thử trên trình duyệt.
- **Frontend hết số demo ở Analytics/Sidebar (2026-09-27)**: `AnalyticsView` nối `GET /api/skills` (điểm 4 kỹ năng, "Not started" nếu chưa có; CEFR lấy từ Writing vì backend chỉ chấm ra CEFR ở đó; thẻ Accuracy +3.5% giả đổi thành "Avg. score" tính từ điểm thật); nút "Start Placement Test" đã gỡ (không có trong spec/backend). Sidebar "cards due" lấy từ `GET /api/vocab/due` qua store `stats.ts` (`dueCards`, tự làm mới sau mỗi thao tác ghi). **Đã test trên trình duyệt thật (2026-09-27)** với tài khoản thử (đã xoá): Analytics/Sidebar/Dashboard hiện đúng số thật ở cả trạng thái rỗng lẫn có dữ liệu; phát hiện và sửa thêm Dashboard (thẻ đến hạn, mastery/CEFR trước đó còn số giả "24 cards", "82%", "+4.2%"; **"phút học trong tuần" và "Pick up where you left off" vẫn là demo cứng** vì backend chưa theo dõi). Phụ đề chạy theo thoại kiểm trên cả 2 phim thật; `is_match` tô MỌI dòng chứa cụm (không chỉ dòng của match), cảnh `demo` không có lớp phủ trùng. Lưu ý môi trường: trên máy này Chrome đôi khi bị `ERR_CONNECTION_RESET` khi gọi `localhost:8000` (Docker Desktop chuyển tiếp IPv6 chập chờn) — dùng `VITE_BACKEND_URL=http://127.0.0.1:8000` nếu gặp.

### 3.15. `docs/schema.sql` đối chiếu toàn diện với DB thật (2026-09-27, đóng mục 4 điểm 12)

> Bối cảnh: mục 4 điểm 12 tồn đọng từ mục 3.13 (2026-09-17) — `docs/schema.sql` (bản "target schema" viết trước khi code) chưa từng được rà lại sau nhiều migration Alembic. Người dùng chọn việc này khi được hỏi nên tiếp tục chức năng chưa xong nào.

- **Phương pháp**: `pg_dump --schema-only` trực tiếp từ `lumina_db` thật (không đọc qua Alembic history), đối chiếu column-by-column/constraint-by-constraint với nội dung cũ của `docs/schema.sql`, viết lại toàn bộ DDL theo đúng cấu trúc thật, giữ lại rationale (ON DELETE, business rule CHECK) gắn vào đúng cột thật. **Test thật, không chỉ đọc bằng mắt** (đúng nguyên tắc mục 5): tạo database rỗng riêng `schema_doc_verify` trên `lumina_db`, áp toàn bộ `docs/schema.sql` mới — 0 lỗi; diff `information_schema.columns`, `pg_constraint`, `pg_indexes` giữa `schema_doc_verify` và `lumina_db` thật — khớp 100%, 0 dòng khác biệt.
- **3 phát hiện quan trọng nhất** (đáng nhớ khi bảo vệ khóa luận):
  1. **Không có Postgres native ENUM nào tồn tại thật trong DB** — quyết định thiết kế gốc ("dùng CREATE TYPE ENUM cho mọi cột enum") chưa từng được thực thi; toàn bộ dùng `VARCHAR(n) + CHECK`, nhất quán trong suốt quá trình implement. Coi là quyết định kiến trúc de facto, cùng loại với việc gọi thẳng `google-generativeai` thay vì qua LangChain (mục 4 điểm 8) — 2 khoảng hở tài liệu-vs-code cùng bản chất, chưa được ghi nhận gộp lại trước đây.
  2. **Bảng `notebook_chat_messages`** (RAG Chat, mục 3.12) tồn tại thật trong DB từ lâu nhưng chưa từng được thêm vào `docs/schema.sql` — đã bổ sung.
  3. **`quiz_attempts.quiz_id` dùng `ON DELETE CASCADE`**, không phải `SET NULL` như nguyên tắc ON DELETE (d) đã công bố ở đầu file — cùng với vài FK nullable khác (`conversation_sessions.scenario_id/persona_id`, `movie_context_tts_fallback.persona_id`, `movie_context_matches.tts_fallback_id/video_subtitle_index_id`) hoàn toàn không khai báo `ON DELETE` (mặc định `NO ACTION`, lẽ ra phải `SET NULL` theo nguyên tắc) — là hạn chế thật, không phải lỗi đánh máy, ghi rõ ở đầu `docs/schema.sql`.
- **Điểm mở mới phát sinh** (ngoài phạm vi lần đối chiếu DDL này, cần việc riêng): index full-text `idx_subtitle_phrase` trên `video_subtitle_index` vẫn dùng cấu hình `'english'` (bỏ stopword), nhưng mục 3.14 ghi rằng service tra cứu đã đổi qua cấu hình `'simple'` để khớp được cụm như "hang out" — cần kiểm tra trực tiếp `movie_context_service.py` xem index này còn được tận dụng hay đã thành sequential scan âm thầm.
- Hầu hết các bảng khác đều lệch tên cột/kiểu dữ liệu đáng kể so với `docs/schema.sql` cũ (vd `transcript_segments` vẫn mô tả theo segment-level dù DB đã đổi sang word-level từ mục 3.13; `conversation_turns`/`rephrase_requests`/`writing_insights` đổi tên gần hết cột) — chi tiết đầy đủ từng bảng nằm trực tiếp trong comment của `docs/schema.sql`, không lặp lại ở đây.

---

## 4. Việc cần làm tiếp (on the horizon)

1. **Xác nhận giá trị enum `error_type`**: đã có đề xuất cụ thể (9 giá trị: `grammar`, `vocabulary`, `spelling`, `pronunciation`, `listening_comprehension`, `reading_comprehension`, `writing_coherence`, `communicative_intent`, `politeness`) trong `docs/api-spec.md` mục 9 — cần rà soát và xác nhận trước khi chạy migration Alembic cho `user_errors`. **Cập nhật (mục 3.10)**: `writing_coherence` nay đã có flow ghi dữ liệu cụ thể (trigger + ngưỡng đề xuất 60/100 trong `docs/schema.sql`) — không còn là giá trị "mồ côi", nhưng bản thân enum 9 giá trị vẫn cần xác nhận chính thức.
2. **Xác nhận nội dung seed data cho `slang_phrases`**: đã có đề xuất quy mô (~80-120 cụm) và tiêu chí chọn nguồn tham chiếu trong `docs/feature-speaking.md` mục 4 — vẫn cần thực sự biên soạn nội dung sau khi quy mô/tiêu chí được xác nhận.
3. **Chốt tên đề tài chính thức** trong số 4 phương án đã đề xuất (mục 1 đề cương).
4. ~~Middleware giới hạn phạm vi route cho token Extension~~ — **đã code (2026-09-25, mục 3.14)**; còn chờ áp migration `20260925_0017` và chạy 2 test `*_integration`. File `services/` trống duy nhất từng còn lại (`movie_context_service`) cũng đã có code.
5. Tiếp tục xây dựng bảng ánh xạ feature-by-technology khi implementation tiến triển.
6. **Xác nhận logic điểm ý định giao tiếp/lịch sự**: đã có đề xuất rubric 0-100 + cấu trúc prompt cụ thể trong `docs/feature-speaking.md` mục 3. Phần schema đã xong (cột `goal`/`formality_level` đã bổ sung vào `scenarios`, có trong `docs/schema.sql`) — điểm còn mở giờ chỉ là **xác nhận bản thân logic/rubric** (không phải thiếu cột nữa).
7. **Xác nhận ý nghĩa phong cách đề `cambridge`** trong tính năng chọn đề bài Viết (Writing Prompt Selection, mục 3.6) — Writing style hay Reading style.
8. **Xác nhận hướng xử lý khoảng hở LangChain-vs-code** (mục 3.12): giữ nguyên gọi thẳng `google-generativeai` và sửa lại tech stack docs cho khớp thực tế, hay refactor `llm_service.py` sang dùng LangChain thật để khớp docs đã viết.
9. **Nâng cấp gói Gemini trả phí trước ngày bảo vệ** (mục 3.12) — free-tier 20 request/ngày/model không đủ cho demo trực tiếp Notebook Chat + Skim & Scan + Writing cùng lúc.
10. ~~Cần key thật cho Podcast~~ — **đã xử lý**: Azure TTS/STT chạy được (mục 3.14), Podcast + Transcript đã có code. Ghi chú gốc (mục 3.13): `AZURE_SPEECH_KEY` (STT, có chỗ trong `.env` nhưng vẫn placeholder) và `ELEVENLABS_API_KEY` (TTS, vừa thêm chỗ trong `Settings`/`.env.example`, chưa có giá trị thật) — chặn build `POST /api/listening/podcasts`/`GET .../transcript` và kết nối `ListeningView.tsx`. Dictation không phụ thuộc 2 key này, đã implement + test xong.
11. ~~Đồng bộ `schema.sql` gốc (root, file init Docker) với DB thật~~ — **ĐÃ XONG (2026-09-17)**: `schema.sql` ở root nay được sinh trực tiếp bằng `pg_dump --schema-only` từ `lumina_db` thật (không viết tay nữa), đã test áp lên 1 database rỗng riêng (`schema_verify_test`) + chạy `alembic upgrade head` từ đầu, xác nhận thành công 100% (0 lỗi) và ra đúng schema y hệt DB thật (kể cả `alembic_version`). Quy ước mới (ghi ngay trong header file `schema.sql`): **mỗi khi có migration Alembic mới, phải sinh lại `schema.sql` gốc trong cùng phiên đó** để không bao giờ lệch nữa như đã từng xảy ra — xem mục 5.
12. ~~`docs/schema.sql` chưa đối chiếu lại với DB thật~~ — **ĐÃ XONG (2026-09-27, mục 3.15)**: sinh lại toàn bộ DDL từ `pg_dump` trên `lumina_db` thật, annotate rationale, test áp lên database rỗng riêng (`schema_doc_verify`) và diff cột/constraint/index với DB thật — khớp 100% (0 diff). Phát hiện quan trọng nhất: DB thật KHÔNG dùng Postgres native ENUM ở đâu cả (toàn VARCHAR+CHECK), và bảng `notebook_chat_messages` (RAG Chat) chưa từng có trong file này. Chi tiết đầy đủ xem `docs/schema.sql` (đầu file) và mục 3.15.

> Các điểm 8-15 từ rà soát lần 3 (đồng bộ ERD/schema, `writing_coherence` mồ côi, ON DELETE, chính sách CHECK constraint, enum `real_video` phụ thuộc tier chưa build, phạm vi token Extension, phiên bản `test-cases (1).md`, thiếu `schema.sql`/`erd.mermaid`) **đã được xử lý toàn bộ** — xem mục 3.10 và `docs/schema.sql`. Khoảng hở tài liệu phát sinh từ đó (mục 3.11 — `api-spec.md`/`test-cases (1).md` chưa phản ánh 2 quyết định) **cũng đã xử lý xong**.

---

## 5. Nguyên tắc làm việc đã thống nhất (áp dụng cho mọi phiên sau)

- **Scope discipline trước tiên**: trước khi đề xuất feature mới, áp dụng framework 3 tầng (Đầy đủ / Thử nghiệm giới hạn / Định hướng mở rộng). Chủ động cảnh báo rủi ro về scope *trước khi* thiết kế chi tiết, không phải sau.
- **Bảo thủ về schema**: ưu tiên mở rộng bảng hiện có trước khi tạo bảng mới. Chỉ tạo bảng mới khi schema hiện tại không thể chứa feature mà không làm biến dạng model.
- **Tách biệt kiến trúc**: logic Content/NLP và hạ tầng audio transport là 2 lớp riêng biệt, phải bàn luận và document tách rời nhau.
- **Khi đưa ra nhiều lựa chọn, luôn đề xuất 1 phương án cụ thể**, không để mở tất cả các lựa chọn.
- **Q&A có cấu trúc** cho các quyết định thiết kế phức tạp (đi qua Q&A rõ ràng trước khi chốt implementation detail).
- **Document-driven continuity**: `lumina_context.md` (file này) là canonical state document; `de_cuong_khoa_luan.md` là đề cương chính thức nộp — cả hai phải được cập nhật đồng bộ khi có quyết định mới. Khi phát hiện hai file lệch nhau (như trường hợp bản đề cương viết lại thiếu phần kiến trúc), cần rà soát và xác nhận lại với người dùng trước khi merge, không tự ý chọn một bên.
- **Khi có bản đề cương mới upload khác với context đang lưu**: luôn so sánh và liệt kê rõ điểm mới / điểm mâu thuẫn trước khi chỉnh sửa, không âm thầm ghi đè.
- **Trước khi giao 1 file SQL/schema thật, chạy thử trên Postgres thật** (không chỉ đọc qua bằng mắt) — đã áp dụng lần đầu ở mục 3.10, nên giữ làm chuẩn cho các lần sinh DDL sau.
- **Khi 1 quyết định được chốt trực tiếp trong `schema.sql`/`erd.mermaid`** (không qua file `.md` mô tả trước — vd trong lúc viết DDL), **phải chủ động rà lại `api-spec.md` và `test-cases (1).md`** xem có chỗ nào vẫn mô tả điểm đó như "chưa quyết định"/"cần làm rõ" hay không, và cập nhật đồng bộ ngay trong cùng phiên — không để tài liệu triển khai/kiểm thử lạc hậu so với schema thật (bài học từ mục 3.11).
- **Trước khi áp dụng bất kỳ migration Alembic mới nào (thay đổi schema DB thật), luôn thông báo cho người dùng và xin phép trước khi chạy** — không tự ý `alembic upgrade` một mình dù migration đã viết idempotent/an toàn. Sau khi migration đã chạy thật, **sinh lại `schema.sql` ở root ngay trong cùng phiên** (`pg_dump --schema-only` từ DB thật, xem hướng dẫn trong header file đó) để file init Docker không bao giờ lệch khỏi DB thật nữa — bài học từ việc phát hiện `schema.sql` gốc đã lệch DB thật từ rất lâu mà không ai biết (mục 3.13, mục 4 điểm 11, chốt 2026-09-17).

### Feature đã cân nhắc và loại bỏ (để tránh đề xuất lại)
- Celebrity voice cloning — rủi ro pháp lý/deepfake.
- Thư viện video lớn được curate thủ công.
- Vocabulary làm phạm vi cho "Rearrange the block".
- Real-time streaming coi là thay đổi content-logic — đã reframe lại thành transport-only upgrade (Định hướng mở rộng, Module 4).
- **Accent vùng miền (regional accent simulation)** — đã cân nhắc ở Mức 2/Thử nghiệm giới hạn (giới hạn 2 accent: Southern US, British) nhưng **quyết định cuối cùng là loại bỏ hoàn toàn**, thay bằng Daily Speaking & Slang. Không đề xuất lại tính năng này trừ khi người dùng chủ động yêu cầu khôi phục.
- **Input đa phương thức mở rộng** (ảnh, PDF, video) — đã thu hẹp còn đúng audio + .docx, áp dụng toàn hệ thống.

---

## 6. Tài liệu tham chiếu khác

- `de_cuong_khoa_luan.md`: đề cương khóa luận chính thức (formal thesis outline) — hiện đã gồm cả phần kiến trúc/thiết kế dữ liệu chi tiết (mục 9-11).
- `thiet_ke_database.md`, `erd_1.mermaid`, `docs/schema.sql`: 3 tài liệu nguồn cho phần dữ liệu chi tiết (được đề cương chính thức tham chiếu tới, không lặp lại toàn bộ) — `erd.mermaid` (sơ đồ) và `schema.sql` (DDL thật, đã test trên PostgreSQL 16 + pgvector) được dựng lần đầu ở rà soát lần 3/mục 3.10; trước đó project chỉ có `thiet_ke_database.md` dạng văn xuôi.
- `docs/feature-reading.md`, `docs/feature-listening.md`, `docs/feature-writing.md`, `docs/feature-speaking.md`, `docs/feature-notebook.md` (mới, mục 3.12): đặc tả kỹ thuật cấp triển khai cho từng module — mục tiêu, input/output, flow, business rules, edge cases, acceptance criteria cho từng chức năng con. Bổ sung cho đề cương (vốn dừng ở mức thiết kế), phục vụ trực tiếp việc code.
- `docs/api-spec.md`: hợp đồng API tổng hợp (route/method/request/response) cho toàn bộ backend, kèm phụ lục đề xuất enum `error_type` và nhật ký đối chiếu ERD (6 mục, đã xử lý hết — mục 3.11).
- `test-cases (1).md`: bộ test case tổng hợp bám theo acceptance criteria/business rules/edge cases của 4 file feature spec — xác nhận là bản chính thức duy nhất (mục 3.10), đã đồng bộ với `schema.sql`/`api-spec.md` (mục 3.11).
- Frontend prototype (Google AI Studio / Gemini-generated React app): chỉ dùng để tham khảo, không tái sử dụng trong implementation thật.

---

## 7. "Chế độ bấm giờ" + Dashboard "This week, in minutes" / "Pick up where you left off" (2026-09-27/28)

> Bối cảnh: 2 khối Dashboard này vẫn là demo cứng (ghi nhận ở mục 3.14). Xác nhận qua code (comment
> trong `DashboardView.tsx`) là điểm "chưa thực hiện xong" duy nhất còn lại dùng được ngay — khác
> các điểm mở khác trong mục 4 (chủ yếu là quyết định/nội dung, không phải code). Khi hỏi hướng xử
> lý, người dùng chọn: xây đo thời gian thật, nhưng chỉ khi nào user chủ động bật "chế độ bấm giờ"
> (không đo ngầm cho ai).

- **Quyết định thiết kế**: không có module nào từng track thời gian học thật trước đây —
  `reading_sessions.time_taken_seconds`/`conversation_sessions.ended_at` có cột trong DB nhưng
  chưa từng được service nào ghi giá trị (cột chết). Giải pháp: bảng mới `study_time_log`
  (user_id, skill, duration_seconds, created_at) + cột `users.timer_mode_enabled` (mặc định
  `false`) — chỉ ghi log khi frontend tự đo và gửi kèm `duration_seconds` lúc nộp bài, hoàn toàn
  không có hoạt động nào tự log khi timer mode tắt.
- **Migration `20260927_0018`** — đã áp lên `lumina_db` thật (test trên bản sao đầy đủ trước, 0 lỗi,
  idempotent khi chạy lại). `schema.sql` gốc đã sinh lại đúng quy ước mục 5.
- **Backend**: `award_activity()` (gamification_service) nhận thêm `duration_seconds` tùy chọn —
  ghi `study_time_log` khi > 0, dùng chung transaction với XP/streak. `GET /api/activity/weekly-summary`
  (tổng phút 7 ngày theo kỹ năng) và `GET /api/activity/recent` (hoạt động gần nhất, gộp từ
  `reading_sessions`/`dictation_attempts`+`podcasts`+`documents`/`writing_submissions`/
  `conversation_sessions`+`scenarios` — không có bảng activity log chung, tính lại mỗi lần đọc như
  `review_priority_queue`). 4 endpoint submit (Reading/Listening/Writing/Speaking) đều nhận
  `duration_seconds` tùy chọn. Test mới `tests/test_activity.py` (6/6 pass) + toàn bộ suite cũ vẫn
  196/196 pass (không regression).
- **Bug thật phát hiện qua test** (không phải yêu cầu ban đầu): `app/routers/auth.py` có 1 hàm
  `user_response()` riêng (trùng với `_user_response` ở `routers/users.py`) — quên cập nhật field
  mới `timer_mode_enabled`, khiến `POST /api/auth/register` lỗi validate. Đã sửa cả 2 nơi.
- **Frontend**: `useStudyTimer.ts` (hook mới, `start()`/`lap()`) nối vào cả 4 view kỹ năng —
  Reading/Listening dùng mốc tạo session/attempt làm điểm bắt đầu (khớp tự nhiên với luồng có
  sẵn); Writing không có bước "tạo phiên" riêng nên tính giờ từ lúc mở tab (mount); Speaking
  `lap()` sau mỗi lượt nói (cộng dồn đúng vì mỗi lượt ghi 1 dòng `study_time_log` riêng, không có
  mốc "kết thúc hội thoại" rõ ràng). `DashboardView.tsx`: "Pick up where you left off" dùng
  `GET /api/activity/recent` 100% thật (bỏ hẳn ảnh minh hoạ stock vì không có ảnh thật cho từng
  hoạt động); "This week, in minutes" có toggle bật/tắt bấm giờ ngay trên card, hiện số thật hoặc
  lời mời bật khi chưa có dữ liệu. `tsc --noEmit` sạch + `vite build` thành công sau cả 2 đợt sửa
  (đọc dữ liệu + nối timer 4 view). **Đã test tay trên trình duyệt thật (2026-09-28)**: đăng ký tài
  khoản mới, bật timer mode (PATCH thật, UI cập nhật đúng), nộp bài Writing 2 lần (24s → làm tròn
  0m đúng, 41s → 1m đúng) — `study_time_log` có dòng thật trong DB, `GET /api/activity/weekly-summary`
  trả đúng số, `GET /api/activity/recent` hiện đúng 2 bài viết theo thứ tự thời gian kèm điểm thật.
  Không có console error nào phát sinh sau khi đăng nhập.
- **Việc cố ý chưa làm**: Skim & Scan (Reading) chưa có bước nộp bài nối backend ở
  `ReadingView.tsx` từ trước (chỉ tạo passage) nên không nối timer ở đó — phát hiện phụ, ngoài
  phạm vi yêu cầu lần này, ghi nhận làm điểm mở mới nếu cần.

---

*Cập nhật lần cuối: mục 7 (2026-09-28) — "Chế độ bấm giờ" + Dashboard "This week, in minutes"/"Pick up where you left off" implement đầy đủ backend (migration đã áp, test thật 6/6 + 196/196 không regression) và frontend (toggle, recent activity thật, timer nối cả 4 view kỹ năng); phát hiện + sửa bug `auth.py` thiếu field `timer_mode_enabled`. Trước đó: mục 3.15 (2026-09-27) — `docs/schema.sql` đối chiếu toàn diện với DB thật (`pg_dump` + test áp trên database rỗng riêng, diff cột/constraint/index khớp 100%), đóng mục 4 điểm 12; phát hiện DB thật không dùng Postgres native ENUM ở đâu cả (VARCHAR+CHECK toàn bộ) và bảng `notebook_chat_messages` chưa từng có trong file thiết kế. Trước đó: mục 3.14 (2026-09-26) — Movie Context (TTS fallback + 3 video demo), middleware token Extension, `/api/extension/lookup` đã code và test với Postgres/Ollama thật; migration 0017 đã áp; xác thực extension chốt là popup login (không build linking cookie). Trước đó: mục 4 điểm 11 (2026-09-17) — `schema.sql` ở root đã đồng bộ lại 100% với DB thật (sinh bằng `pg_dump`, test qua database rỗng + `alembic upgrade head` thành công 0 lỗi); thêm quy ước bắt buộc vào mục 5: xin phép trước khi chạy migration mới + sinh lại `schema.sql` ngay sau khi migration chạy. Trước đó: mục 3.13 (2026-09-17) — implement Dictation (Module 2 Listening) chạy được + test thật (28/28 pass, không phụ thuộc Gemini), phát hiện DB thật khởi tạo từ `schema.sql` gốc (prototype cũ) chứ không phải `docs/schema.sql` (mục 4 điểm 12, vẫn mở — khác điểm 11 đã xong), Podcast/Transcript vẫn chờ ElevenLabs/Azure Speech key thật (mục 4 điểm 10), chưa kết nối `ListeningView.tsx`. Trước đó nữa: mục 3.12 (2026-09-16) — bắt đầu implementation thật (Auth/Notebook/Reading/Vocab/Writing chạy được trên Postgres + Gemini thật), thêm RAG Chat và Skim & Scan gắn tài liệu thật theo yêu cầu người dùng, phát hiện + sửa lỗi xử lý khi Gemini lỗi (`AIServiceError`), phát hiện khoảng hở tài liệu LangChain-vs-code cần người dùng xác nhận hướng xử lý (mục 4 điểm 8).*
