
# Thiết kế Database — Nền tảng học tiếng Anh ứng dụng AI

## 1. Nguyên tắc thiết kế

Thay vì tạo một nhóm bảng riêng cho từng tính năng (dẫn đến trùng lặp và khó mở rộng), schema được xây dựng quanh **6 nhóm thực thể lõi** mà phần lớn tính năng tái sử dụng, cộng thêm các bảng đặc thù cho phần logic khác biệt của từng tính năng:

| Nhóm lõi | Vai trò |
|---|---|
| `users` | Danh tính người học, cấu hình cá nhân |
| `documents` + `document_chunks` | Tài liệu người dùng tải lên (audio hoặc .docx) + dữ liệu RAG (dùng chung cho Notebook, Podcast, Classic Mode, Writing...) |
| `learning_attempt` (khái niệm chung, cụ thể hóa theo từng bảng con) | Mọi lượt tương tác học đều gắn với 1 `user_id` + `document_id` (nullable nếu không gắn tài liệu) |
| `quiz_attempts` + `user_errors` | Nơi tổng hợp lượt làm bài và lỗi từ **mọi** tính năng (ngữ pháp, phát âm, từ vựng, ý định giao tiếp...) — đây là cặp bảng trung tâm nuôi thuật toán ưu tiên ôn tập, không phải bảng riêng của tính năng nào. `user_errors` gắn nhãn phân loại theo enum `error_type` cố định (giá trị cụ thể chưa chốt — xem mục 6) |
| `personas` | Thư viện giọng nói hợp lệ dùng chung cho Podcast, AI Conversation Partner, TTS phản hồi (không còn bảng `accents` — đã loại bỏ mô phỏng giọng vùng miền) |
| `review_priority_queue` | Hàng đợi ôn tập tổng hợp từ `vocab_reviews` + `user_errors`, dùng chung cho Spaced Repetition và Dynamic Quiz Generator |

Việc đặt `quiz_attempts`/`user_errors` và `review_priority_queue` làm cặp bảng trung tâm (thay vì để mỗi tính năng tự lưu lỗi riêng) chính là điểm giúp tính năng "nhật ký lỗi xuyên suốt 4 kỹ năng" (USP cốt lõi của đề tài) hoạt động đúng — nếu không có tầng tổng hợp này, thuật toán ưu tiên ôn tập sẽ không thể nhìn xuyên suốt Đọc/Nghe/Viết/Nói.

*Ghi chú lịch sử thiết kế: bảng `error_log` tổng hợp chung ban đầu đã được tách thành `quiz_attempts` (nhật ký lượt làm bài) + `user_errors` (từng lỗi riêng lẻ, có nhãn phân loại) để phục vụ trực tiếp tính năng Rearrange the Block (phân loại lỗi hybrid rule-based/Gemini structured output) — xem `error_tracking_service.py` trong kiến trúc hệ thống.*

## 2. Ánh xạ bảng theo mức ưu tiên (khớp mục 5.2 đề cương)

**Đầy đủ (MVP):** `users`, `documents`, `notebook_folders`, `document_chunks`, `generated_passages`, `vocab_items`, `vocab_reviews`, `reading_sessions`, `reading_answers`, `contextual_guess_attempts`, `custom_stories`, `podcasts`, `transcript_segments`, `dictation_attempts`, `writing_submissions`, `writing_insights`, `rephrase_requests`, `quiz_attempts`, `user_errors`, `review_priority_queue`, `quizzes`, `streaks`, `skill_progress`, `personas`.

**Thử nghiệm giới hạn:** `scenarios`, `conversation_sessions`, `conversation_turns`, `slang_phrases`, `user_phrasebook_entries`, `movie_context_tts_fallback`, `movie_context_matches` (nhánh dự phòng — đọc mẫu bằng TTS, triển khai trước vì đơn giản, không phát sinh rủi ro nội dung); bổ sung cho Browser Extension: cột `client_type` trên `refresh_tokens`, cột `source_url` (nullable) trên `vocab_items`.

**Định hướng mở rộng:** `realtime_conversation_metrics` (mở rộng streaming cho Conversation Partner), `video_sources`, `video_subtitle_index` (nhánh tìm video thật — mục tiêu ưu tiên nhưng phức tạp hơn, triển khai sau nếu còn thời gian; **cập nhật mục 10**: 2 bảng này đã được tạo sẵn trong `docs/schema.sql` dù logic chưa implement, để tránh phải ALTER thêm khi làm nhánh video thật sau này).

## 3. Vài quyết định thiết kế cần lưu ý khi trình bày trong khóa luận

- **`document_chunks.embedding`** dùng kiểu `vector(768)`. **Cập nhật (2026-09-16)**: model embedding thật dùng là `models/gemini-embedding-001` (gọi `google-generativeai` trực tiếp, không qua LangChain — xem mục 11) với `output_dimensionality=768`, KHÔNG phải `text-embedding-004` như mô tả gốc — model đó đã bị Google deprecated (xác nhận qua `ListModels` thật với API key của project, trả lỗi 404 khi gọi). Nếu đổi model embedding khác, chiều vector phải đổi theo, nên đây vẫn là điểm cấu hình cần theo dõi khi Google thay đổi model lineup.
- **`conversation_turns`** lưu cả điểm phát âm, điểm ý định giao tiếp và điểm lịch sự trên **cùng một dòng** (turn), phản ánh đúng kiến trúc turn-based đã thống nhất — không tách thành 2 bảng Shadowing/Roleplay riêng như thiết kế cũ.
- **`realtime_conversation_metrics`** để trống ở tier Đầy đủ/Thử nghiệm giới hạn, chỉ kích hoạt khi nâng cấp lên streaming thời gian thực (Định hướng mở rộng) — tách riêng để không phá vỡ schema hiện có khi mở rộng sau này.

## 4. Đối chiếu với prototype "Lumina" (Google AI Studio) — phát hiện và điều chỉnh

Prototype được cung cấp là **giao diện demo không có tầng lưu trữ** (React state + gọi thẳng Gemini API one-shot qua Express), nên không phản ánh kiến trúc backend, nhưng cho thấy **hình dạng dữ liệu thực tế** của từng tính năng — từ đó phát hiện một số điểm schema ban đầu chưa khớp:

| Phát hiện từ prototype | Điều chỉnh trong schema |
|---|---|
| "Contextual Guessing" và câu hỏi Skim & Scan thực chất là **bài tập trắc nghiệm** (có sẵn đáp án lựa chọn), không phải để AI chấm câu trả lời tự do | `reading_answers` và `contextual_guess_attempts` đổi từ `guess_text`/`ai_score` sang `options` (JSONB) + `correct_option_index` + `selected_option_index` |
| `VocabWord` có `synonyms`/`antonyms` | Thêm 2 cột này vào `vocab_items` |
| Notebook có folder phân loại, tag, đánh dấu sao, dung lượng file | Thêm bảng `notebook_folders` + cột `folder_id`, `tags`, `starred`, `file_size_kb` vào `documents` |
| Kết quả Writing Analysis có 3 loại insight khác cấu trúc nhau (grammar có offset, vocabulary có synonyms, style có suggestion viết lại cả câu) | Gộp `grammar_corrections` thành bảng đa hình `writing_insights` với các cột tùy loại; thêm `cefr_level`/`ielts_band` vào `writing_submissions` |
| Phản hồi hội thoại AI trả về `correctedText`, `cefrTip`, `grammarTip`, `pronunciationAdvice` — nhưng **không có** điểm số ý định giao tiếp/lịch sự riêng biệt như đề cương mô tả | Bổ sung các cột nội dung phản hồi vào `conversation_turns`; giữ `intent_score`/`politeness_score` nhưng cho phép NULL vì đây là phần **chưa được xác nhận triển khai** trong prototype — cần làm rõ với giảng viên đây là phần nhóm sẽ tự xây thêm |
| Movie Delivery Context trong prototype là **AI bịa ra cảnh phim hư cấu**, nhưng UI lại ghi nhãn "Real Native Dialogue" | Thiết kế lại thành mô hình hybrid: `video_sources`/`video_subtitle_index` (thật, ưu tiên) + `movie_context_examples` (AI sinh, dự phòng) + `movie_context_matches` hợp nhất kết quả, ràng buộc `CHECK` đảm bảo mỗi kết quả chỉ đến từ đúng 1 nguồn. **Nếu dùng nhánh AI-generated, nhãn UI phải nêu rõ đây là nội dung minh họa do AI tạo ra, không phải hội thoại thật**, để tránh đánh lừa người học — đây là điểm nên nêu chủ động với giảng viên như một cân nhắc đạo đức thiết kế sản phẩm |
| Dashboard hiển thị điểm + cấp độ CEFR theo từng kỹ năng riêng biệt | Thêm bảng `skill_progress` |
| `ErrorJournalItem` có `spacedRepetitionLevel` ngay trên chính lỗi (không qua bảng SM-2 riêng như từ vựng) | Thêm cột `spaced_repetition_level` trực tiếp vào `user_errors` — đơn giản hơn SM-2 đầy đủ, phù hợp vì lỗi ngữ pháp/phát âm không cần độ chính xác lịch ôn tập cao như từ vựng |

### Điểm cần lưu ý khi trình bày

- Vì prototype không có backend thật, **không nên trích dẫn nó như bằng chứng kiến trúc đã được kiểm chứng** trong báo cáo — chỉ nên dùng để minh họa UI/UX và đối chiếu hình dạng dữ liệu, đúng như cách đã làm ở đây.
- Sự khác biệt giữa đề cương (có điểm ý định giao tiếp/lịch sự) và prototype (không có) là dấu hiệu cho thấy phần "chấm điểm ý định giao tiếp" trong AI Conversation Partner **chưa có thiết kế prompt/logic cụ thể** — nên xử lý phần này sớm vì nó ảnh hưởng trực tiếp đến bảng `conversation_turns` và tiêu chí đánh giá hệ thống (mục 6 đề cương).

## 5. Cập nhật sau khi đơn giản hóa Movie Delivery Context + rà soát toàn diện lần 2

Theo quyết định đơn giản hóa nhánh dự phòng (bỏ "AI bịa cảnh phim", thay bằng đọc mẫu câu qua TTS để nghe và luyện đọc nhại), mình rà lại **toàn bộ** đối chiếu đề cương ↔ schema một lần nữa và phát hiện thêm 2 điểm cần sửa (không liên quan Movie Context nhưng bị bỏ sót ở các lần trước):

| Phát hiện | Vấn đề | Điều chỉnh |
|---|---|---|
| **Movie Delivery Context — nhánh dự phòng** | `movie_context_examples` (bịa cảnh phim) không còn phù hợp | Thay bằng `movie_context_tts_fallback` (chỉ lưu `phrase_text` + `audio_url` đọc mẫu bằng giọng từ `personas`), `movie_context_matches` cập nhật `source_type` thành `'real_video'` \| `'tts_fallback'` |
| **Skim & Scan sinh đoạn văn mới, không gắn với tài liệu Notebook** | `reading_sessions.document_id` trước đó là `NOT NULL`, nhưng theo `server.ts` (`/api/ai/generate-story`), Skim & Scan **sinh đoạn văn hoàn toàn mới theo chủ đề/trình độ**, độc lập với tài liệu người dùng tải lên — nếu giữ ràng buộc cũ, tính năng này sẽ không thể lưu được kết quả | Thêm bảng `generated_passages`; `reading_sessions.document_id` chuyển thành nullable, thêm `generated_passage_id`, ràng buộc `CHECK` đảm bảo Classic Mode dùng `document_id`, Skim & Scan dùng `generated_passage_id` |
| **Đoán nghĩa ngữ cảnh áp dụng cho từ chưa lưu** | `contextual_guess_attempts.vocab_item_id` trước đó `NOT NULL`, nhưng thử thách điền khuyết được sinh ngay khi tra bất kỳ từ nào (kể cả khi người dùng chưa bấm "lưu vào sổ từ vựng") | `vocab_item_id` chuyển thành nullable, thêm cột `term` lưu trực tiếp từ đang tra để không phụ thuộc việc từ đó đã được lưu hay chưa |

### Kết luận sau 2 lần rà soát

Sau khi đối chiếu toàn bộ mục 5.2/6/8 của đề cương với các bảng trong `schema.sql`, **không còn tính năng nào bị thiếu bảng lưu trữ tương ứng**. Các bảng còn lại (`writing_insights`, `skill_progress`, `quiz_attempts`, `user_errors`, `review_priority_queue`...) đã được xác nhận khớp ở lần rà soát trước và không có thay đổi thêm. Điểm duy nhất cần bạn tiếp tục theo dõi là phần điểm ý định giao tiếp/lịch sự trong `conversation_turns` (đã nêu ở mục 4) — vẫn là phần thiết kế logic chưa được xác nhận bằng prototype.

## 6. Bổ sung sau khi tích hợp Daily Speaking & Slang và Browser Extension

- **Sổ tay Slang/Cụm thoại**: thêm `slang_phrases` (thư viện cụm từ tham chiếu, có nguồn và mức độ trang trọng) và `user_phrasebook_entries` (bản ghi người học lưu lại, tham chiếu nullable độc lập tới `slang_phrases.id` và `conversation_turns.id`).
- **Browser Extension**: thêm cột `client_type` (`'web'` | `'extension'`) trên `refresh_tokens` để phân biệt nguồn phát hành token, phục vụ cơ chế "linking cookie"; thêm cột `source_url` (nullable) trên `vocab_items` để lưu URL trang ngoài khi từ được tra qua extension. **Cập nhật mục 10**: phạm vi token extension khi gọi API đã được chốt (chỉ `/api/extension/*` + `/api/reading/lookup` + `/api/vocab`), enforce bằng middleware đọc `client_type`, không cần thêm cột.
- **Giá trị enum `error_type`** cho `user_errors` vẫn là điểm còn mở, cần chốt trước khi chạy migration Alembic cho bảng này.

## 7. Bổ sung sau khi mở rộng Viết luận thành 3 nguồn đề bài

Theo yêu cầu mở rộng tính năng Viết (Module 3): thay vì chỉ có 1 loại đề "tóm tắt tài liệu" (Summary Essay), người học giờ chọn được 1 trong 3 nguồn đề bài — tóm tắt tài liệu, chủ đề mở rộng liên quan tài liệu, hoặc chủ đề tự chọn (kèm gợi ý theo phong cách chứng chỉ TOEIC/IELTS/Cambridge). Đây là **mở rộng ngoài phạm vi mô tả gốc trong đề cương/prototype ban đầu** (mục 4 chỉ ghi nhận "Summary Essay"), cần bổ sung schema như sau:

**`writing_submissions`** — thêm 3 cột:

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| `source_type` | enum | `NOT NULL` | `'document_summary'` \| `'extended_topic'` \| `'free_topic'` |
| `prompt_text` | text | `NOT NULL` | Đề bài cụ thể đã chọn/được sinh ra, lưu lại để hiển thị và tái sử dụng, không cần sinh lại khi xem lại bài |
| `certificate_style` | enum, nullable | — | `'toeic'` \| `'ielts'` \| `'cambridge'`; chỉ set khi `prompt_text` được sinh qua gợi ý phong cách chứng chỉ (nhánh `free_topic`) |

**Ràng buộc nghiệp vụ**:
- `source_type = 'extended_topic'`: bắt buộc `document_id` khác NULL (dùng tài liệu làm cơ sở mở rộng chủ đề).
- `source_type = 'document_summary'`: `document_id` khác NULL, `document_chunks` liên quan được dùng làm ground truth chấm coverage.
- `source_type = 'free_topic'`: `document_id` luôn NULL — không phụ thuộc tài liệu.
- `source_type` khác `'document_summary'` (tức `'extended_topic'`/`'free_topic'`) **không** dùng `document_chunks` để chấm coverage — 2 loại này chấm theo 1 rubric chung 4 tiêu chí (Task Response, Coherence & Cohesion, Lexical Resource, Grammatical Range & Accuracy), không phải rubric coverage như Summary.

> **Cập nhật mục 10 (đã thay đổi so với đoạn gốc bên dưới)**: ban đầu mục này ghi "không bắt buộc CHECK constraint ở DB vì logic phụ thuộc `source_type`". Sau khi viết `docs/schema.sql` (giải quyết điểm mở #11 về chính sách CHECK chưa nhất quán), ràng buộc trên **đã được áp bằng `CHECK` thật ở DB** (`chk_writing_submissions_source_type`), nhất quán với cách `reading_sessions`/`vocab_items` đang làm, thay vì chỉ validate ở tầng service như dự định ban đầu.

**Quyết định thiết kế cần lưu ý khi trình bày**: cân nhắc xây riêng 3 rubric chấm điểm khớp chuẩn thật của TOEIC/IELTS/Cambridge, nhưng quyết định **dùng chung 1 rubric** cho `extended_topic`/`free_topic` để kiểm soát phạm vi triển khai — phong cách chứng chỉ chỉ ảnh hưởng cách Gemini **sinh đề bài** (độ dài, dạng câu hỏi, văn phong kỳ vọng), không ảnh hưởng cách **chấm điểm**. Cần nêu rõ giới hạn này khi bảo vệ khóa luận: hệ thống mô phỏng phong cách đề bài của các chứng chỉ, không cam kết độ chính xác chấm điểm tương đương giám khảo thật của từng chứng chỉ.

Không phát sinh bảng mới cho phần mở rộng này — đúng nguyên tắc bảo thủ về schema (mục 1), chỉ mở rộng `writing_submissions` hiện có (mục 10 bổ sung thêm 1 cột nữa: `rubric_scores`, phục vụ flow `writing_coherence`).

Chi tiết flow/business rules/API xem `docs/feature-writing.md` mục 1 và `docs/api-spec.md` mục 5; đối chiếu đề cương xem `de_cuong_khoa_luan.md` mục 9.7.

## 8. Bổ sung sau khi thêm STT fallback (Azure ưu tiên, Whisper dự phòng) cho Speaking

Theo quyết định mục 3.8 `lumina_context.md`: nhánh STT thuần của Speaking (lấy transcript cho LLM) giờ có fallback sang Whisper khi Azure STT lỗi/timeout. Nhánh Pronunciation Assessment (chấm âm vị) không có fallback — vẫn chỉ Azure.

**`conversation_turns`** — thêm 1 cột:

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| `stt_provider_used` | enum | `NOT NULL` | `'azure'` \| `'whisper'` — ghi lại provider thực tế đã xử lý STT cho lượt nói đó, phục vụ theo dõi tần suất fallback |

Không phát sinh bảng mới — đúng nguyên tắc bảo thủ về schema (mục 1), chỉ mở rộng `conversation_turns` hiện có. Cột này nằm ở tier **Thử nghiệm giới hạn** (cùng tier với `conversation_turns` — xem mục 2), không phải tier riêng.

Chi tiết flow/business rules xem `docs/feature-speaking.md` mục 1.3-1.6; đối chiếu đề cương xem `de_cuong_khoa_luan.md` mục 9.4.

## 9. Bổ sung sau rà soát đối chiếu DB lần 3 (`reading_answers`, `quizzes`/`quiz_attempts`)

Theo 2 quyết định đã chốt trong `lumina_context.md` mục 3.9 (rà soát toàn diện lần 3, phát hiện qua đối chiếu chéo `thiet_ke_database.md` với `feature-reading.md`/`api-spec.md`/`test-cases (1).md`):

### 9.1. `reading_answers` — thêm cột trích dẫn riêng cho Skim & Scan

Bản sửa mục 5 (rà soát lần 2) đã xử lý XOR cho `reading_sessions` (`document_id` / `generated_passage_id`), nhưng bỏ sót `reading_answers` — cột `source_chunk_id` ở đó vốn chỉ có nghĩa với Classic Mode (trích dẫn từ `document_chunks`). Skim & Scan trích dẫn theo vị trí trong `generated_passages.content` (offset/chunk nội bộ của passage, không qua `document_chunks` — đúng `feature-reading.md` mục 2.3), nên hiện chưa có chỗ lưu trích dẫn hợp lệ cho các session Skim & Scan.

**`reading_answers`** — điều chỉnh:

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| `source_chunk_id` | uuid, FK → `document_chunks.id` | nullable (đổi từ NOT NULL) | Chỉ set khi `reading_sessions.mode = 'classic'` |
| `passage_citation_ref` | JSONB, nullable | — | **Mới.** Lưu vị trí trích dẫn trong `generated_passages.content` (ví dụ `{ "offset_start": int, "offset_end": int }`, hoặc chỉ số chunk nội bộ tự sinh lúc tạo câu hỏi) — chỉ set khi `reading_sessions.mode = 'skim_scan'` |

**Ràng buộc**: thêm `CHECK` đảm bảo đúng 1 trong 2 cột (`source_chunk_id` / `passage_citation_ref`) có giá trị — nhất quán với cách `reading_sessions` đã làm ở mục 5 (đây vẫn là XOR 2 cột đơn giản, không phải logic 3 nhánh phụ thuộc như `writing_submissions` ở mục 7, nên áp CHECK ở DB thay vì chỉ validate tầng service).

**Đã implement**: xem `CREATE TABLE reading_answers` trong `docs/schema.sql` (đã test chạy thật).

> **Đính chính (2026-09-24, mục 12)**: `passage_citation_ref` và CHECK XOR **chưa từng có trong DB thật** (`schema.sql` gốc/pg_dump) — câu "đã implement" ở trên chỉ đúng với `docs/schema.sql` bản thiết kế. `reading_service.create_skim_scan_session` hiện sinh câu hỏi bằng LLM không kèm vị trí trích dẫn, nên các câu Skim & Scan có cả 2 cột đều NULL. Đã bỏ cột này khỏi `docs/schema.sql`/ERD cho khớp thực tế; thêm lại khi prompt sinh câu hỏi trả offset.

### 9.2. `quizzes` — làm rõ phạm vi và quan hệ với `quiz_attempts`

`quizzes` trước đó nằm trong danh sách bảng MVP (mục 2) nhưng chưa từng có mô tả cấu trúc/quan hệ ở đâu. Bằng chứng từ `api-spec.md`: `POST /api/adaptive/quizzes/generate` trả về `quiz_id` + `questions`, còn `POST /api/reading/rearrange` và `POST /api/writing/rearrange` chỉ trả `attempt_id` + `blocks` — không có `quiz_id` nào. Điều này xác nhận `quizzes` chỉ phục vụ đề động do Adaptive Learning Engine sinh; Rearrange the Block không đi qua bảng này.

**`quizzes`** (mô tả cấu trúc lần đầu — MVP, tên bảng đã có sẵn trong danh sách mục 2 từ trước):

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| `id` | uuid | PK | |
| `user_id` | uuid, FK → `users.id` | NOT NULL | |
| `focus_error_types` | JSONB, nullable | — | Danh sách `error_type` được yêu cầu tập trung khi sinh đề, khớp tham số `focus_error_types` của `POST /api/adaptive/quizzes/generate` |
| `questions` | JSONB | NOT NULL | Bộ câu hỏi đã sinh, trả nguyên cho client khi tạo và khi xem lại |
| `created_at` | timestamp | NOT NULL | |

**`quiz_attempts`** — thêm 1 cột:

| Cột | Kiểu | Ràng buộc | Ghi chú |
|---|---|---|---|
| `quiz_id` | uuid, FK → `quizzes.id` | nullable | Chỉ set khi lượt làm bài thuộc 1 bộ đề đã sinh qua Adaptive Engine. Luôn NULL với các dòng `quiz_attempts` của Rearrange the Block (Reading/Writing) — 2 tính năng này tiếp tục ghi thẳng `quiz_attempts` như thiết kế gốc, không tạo `quizzes` |

**Quan hệ**: `quizzes` (1) — `quiz_attempts` (nhiều): 1 bộ đề có thể được làm lại nhiều lần, mỗi lần là 1 `quiz_attempts` mới, cùng trỏ về 1 `quizzes`.

Không phát sinh bảng mới ngoài việc mô tả cụ thể `quizzes` (tên bảng vốn đã có trong danh sách MVP) — đúng nguyên tắc bảo thủ về schema (mục 1).

**Đã implement**: xem `CREATE TABLE quizzes` và `quiz_attempts.quiz_id` trong `docs/schema.sql` (đã test chạy thật).

### 9.3. Điểm còn mở liên quan schema — ĐÃ XỬ LÝ TOÀN BỘ (xem mục 10)

Rà soát lần 3 từng phát hiện thêm 6 điểm mở khác (quy tắc `ON DELETE`, chính sách `CHECK` constraint chưa nhất quán, `error_type = WRITING_COHERENCE` chưa có flow ghi dữ liệu, `movie_context_matches.source_type = 'real_video'` phụ thuộc tier chưa build, phạm vi token Extension, phiên bản file `test-cases (1).md`) — **toàn bộ đã được xử lý** khi viết `docs/schema.sql`, xem mục 10 ngay bên dưới và `lumina_context.md` mục 3.10.

## 10. `schema.sql` — DDL thật đầu tiên của project (PostgreSQL 16 + pgvector)

Đã sinh `docs/schema.sql`, chuyển toàn bộ thiết kế văn xuôi ở mục 1-9 thành DDL cụ thể. **Đã test chạy thật** trên PostgreSQL 16 + pgvector 0.6.0 (không chỉ đọc qua bằng mắt): tạo database sạch, áp toàn bộ file không lỗi, chạy functional test cho các CHECK constraint chính, `ON DELETE CASCADE`, trigger tự động, và truy vấn similarity qua index HNSW.

**3 quyết định mới khi viết schema.sql (giải quyết các điểm mở còn lại của mục 9.3):**

1. **`writing_submissions.rubric_scores`** (JSONB, mới) — lưu 4 tiêu chí (`task_response`, `coherence_cohesion`, `lexical_resource`, `grammatical_range_accuracy`, thang 0-100), chỉ dùng cho `extended_topic`/`free_topic`. Trigger `trg_writing_submissions_flag_coherence` tự động ghi `user_errors(error_type='writing_coherence')` khi `coherence_cohesion < 60` lúc bài vừa chấm xong — giải quyết dứt điểm việc `writing_coherence` là giá trị "mồ côi" trong enum `error_type`. Ngưỡng 60/100 là đề xuất, cần xác nhận lại.
2. **Chính sách `ON DELETE`** — áp dụng nhất quán theo 4 nguyên tắc (CASCADE từ `users`; CASCADE cho các quan hệ tham gia CHECK dạng XOR; RESTRICT cho bảng thư viện dùng chung như `scenarios`/`personas` khi cột NOT NULL; SET NULL cho tham chiếu optional thuần túy) — chi tiết đầu file `schema.sql`.
3. **Chính sách `CHECK` constraint** — nay nhất quán trên toàn schema: `writing_submissions` có thêm `CHECK` (trước đó chỉ định ở mục 7 là validate tầng service), cùng cách tiếp cận với `reading_sessions`/`vocab_items`/`reading_answers`/`movie_context_matches`.

**Đã tạo sẵn schema cho nhánh `real_video`**: `video_sources`/`video_subtitle_index` (tier Định hướng mở rộng, logic chưa implement) đã có trong `schema.sql`, để `movie_context_matches.source_type = 'real_video'` có FK hợp lệ ngay từ đầu.

**Phạm vi token Extension**: chốt logic (chỉ gọi được `/api/extension/*` + `/api/reading/lookup` + `/api/vocab`) nhưng đây là chính sách tĩnh, không cần cột DB riêng — enforce bằng middleware đọc `refresh_tokens.client_type`, còn là TODO code (xem `lumina_context.md` mục 4 điểm 4).

## 11. Bổ sung sau khi implement RAG Chat (Notebook) và Skim & Scan gắn tài liệu thật (2026-09-16)

Migration `20260917_0006` (backend) thêm:

1. **`notebook_chat_messages`** (bảng mới) — lịch sử hội thoại RAG kiểu NotebookLM, 1 document có 1 luồng chat. Cột: `id`, `document_id` (FK CASCADE), `user_id` (FK CASCADE), `role` (`CHECK IN ('user','assistant')`), `content` (text), `sources` (JSONB, chỉ set cho `role='assistant'` — mảng `{chunk_id, excerpt}`), `created_at`. Xem `feature-notebook.md` mục 2.
2. **`generated_passages.source_document_id`** (cột mới, nullable, FK → `documents` `ON DELETE SET NULL`) — khác `NULL` khi Skim & Scan dùng excerpt thật từ tài liệu user thay vì AI tự sinh theo topic. Xem `feature-reading.md` mục 2 (đã cập nhật cùng ngày) — đây là thay đổi hành vi so với mô tả gốc ở mục 5 file này ("Skim & Scan sinh đoạn văn mới, không gắn với tài liệu Notebook"), theo yêu cầu trực tiếp của người dùng.

**Phát hiện lệch tài liệu cần lưu ý khi trình bày khóa luận**: bảng tech stack (`lumina_context.md` mục 2) ghi "LangChain dùng để trừu tượng hóa Gemini", nhưng code thật (`backend/app/services/llm_service.py`, `rag_service.py`) gọi thẳng SDK `google-generativeai`, **không** qua LangChain ở bất kỳ đâu (`grep langchain` trên toàn bộ `backend/app` không có kết quả, dù `langchain`/`langchain-google-genai` vẫn nằm trong `requirements.txt`). Đây là khoảng hở tài liệu-vs-code có sẵn từ trước (không phát sinh trong phiên này), chỉ được phát hiện khi implement RAG Chat cần đọc kỹ `llm_service.py`. Không refactor lại trong phiên này (ngoài phạm vi yêu cầu, và cách gọi trực tiếp đã chứng minh hoạt động ổn định qua nhiều lần test thật) — cần người dùng xác nhận hướng xử lý: (a) cập nhật tech stack docs cho khớp thực tế, hoặc (b) refactor `llm_service.py` sang dùng LangChain thật để khớp docs.

Xem toàn bộ SQL cụ thể, comment giải thích từng quyết định, và ghi chú "chưa xử lý trong lần này" (enum `error_type` chính thức, seed `slang_phrases`, tên đề tài, logic điểm ý định/lịch sự, nghĩa `cambridge`) trực tiếp trong `docs/schema.sql` và `lumina_context.md` mục 3.10/mục 4.

## 12. Rà soát toàn vẹn DB thật (2026-09-24, migration `20260924_0015`)

Đối chiếu tài liệu với DB đang chạy (`schema.sql` gốc = pg_dump) và code. **Nguồn DDL chuẩn duy nhất là `schema.sql` ở thư mục gốc**; `docs/schema.sql` chỉ để giải thích thiết kế (tên một số cột khác bản thật: `session_id`/`submission_id` → `reading_session_id`/`writing_submission_id`, `text/start_ms` → `word_text/start_time_ms`).

### 12.1. Lỗi đã sửa (đã tái hiện trên DB thật trước khi sửa)

| Vấn đề | Nguyên nhân | Sửa |
|---|---|---|
| Xoá document lỗi 500 khi đã lưu từ vựng từ tài liệu đó hoặc có bài Writing `document_summary`/`extended_topic` | FK `document_id ON DELETE SET NULL` mâu thuẫn với CHECK bắt `document_id NOT NULL` | Giữ SET NULL (không mất dữ liệu học của user), nới CHECK: `vocab_items` chỉ cấm có cả 2 nguồn (API vẫn bắt đúng 1 nguồn khi tạo); `writing_submissions` chỉ cấm `free_topic` có document. `submit_essay` trả 404 `document_not_found` nếu tài liệu của bài `document_summary` đã bị xoá |
| RAG quét tuần tự | Provider mặc định (Ollama) dùng `embedding_local` nhưng cột này không có index; `embedding` dùng ivfflat tạo lúc bảng rỗng | HNSW cho cả `embedding` và `embedding_local` |
| `writing_coherence` không có flow ghi | Trigger mô tả ở mục 10 chưa từng tồn tại trong DB | Ghi ở tầng service: `writing_service.submit_essay` gọi `record_error` khi `coherence_cohesion < 60` (ngưỡng vẫn là đề xuất) |

### 12.2. Đồng bộ tài liệu ↔ DB

- Bỏ bảng cũ `error_log`, `accents` (0 dòng, không code dùng).
- `passage_citation_ref` chưa implement — xem đính chính ở mục 9.1.
- `dictation_attempts.podcast_id`: `ON DELETE CASCADE` + `NOT NULL` (trước đó DB là SET NULL/nullable, lệch model).
- `reading_answers.source_chunk_id`: `ON DELETE SET NULL` (trước đó NO ACTION).
- Model SQLAlchemy: cột thời gian dùng `DateTime(timezone=True)` khớp `timestamptz`; khai báo FK `conversation_sessions.persona_id`.
- `skill_progress`: đã có model `SkillProgress` và code ghi/đọc — xem 12.4.
- Embedding: mặc định bge-m3 (1024 chiều) qua Ollama, Gemini 768 chiều là tuỳ chọn.

### 12.3. Cải tiến

- Index cho mọi FK có `ON DELETE` (reading_sessions, reading_answers, vocab_items, contextual_guess_attempts, writing_submissions, podcasts, dictation_attempts, user_errors, user_phrasebook_entries).
- UNIQUE `(podcast_id, word_index)` trên `transcript_segments`, `(conversation_session_id, turn_index)` trên `conversation_turns`.
- CHECK cho cột enum dạng chuỗi: `documents.source_type/status`, `podcasts.status`, `quiz_attempts.attempt_type`, `conversation_sessions.status`, `writing_insights.insight_type`, `review_priority_queue.item_type`.
- Hàng đợi ôn tập: lỗi đã ôn đúng (`spaced_repetition_level > 0`) không còn được cộng điểm "mới xảy ra".

### 12.4. Hoàn thiện phần còn lại (migration `20260924_0016`)

- **Chống lưu trùng từ vựng**: UNIQUE index `uq_vocab_items_user_term` trên `(user_id, lower(term))`. `POST /api/vocab` kiểm tra trước và trả `409 vocab_duplicate` (kể cả khi 2 request đồng thời — `IntegrityError` cũng được dịch thành 409). Migration tự gộp dữ liệu trùng đã có (giữ bản cũ nhất, chuyển `contextual_guess_attempts`/`custom_stories` sang bản giữ lại; `vocab_reviews` của bản bị gộp bị xoá theo CASCADE).
- **`skill_progress` (Dashboard điểm theo kỹ năng)**: model `SkillProgress`; `gamification_service.award_activity(..., score=, cefr_level=)` cập nhật cùng transaction với XP/streak. Điểm chuẩn hoá về thang 0-100 và là **trung bình động** (điểm mới chiếm 30%, hằng `SKILL_SCORE_WEIGHT` — đề xuất của nhóm, chưa có trong đề cương): reading = `score × 100`, listening = `accuracy_score` của Dictation, writing = `overall_score` (kèm `cefr_level` do LLM ước lượng), speaking = điểm phát âm của lượt (lượt phát âm lỗi không góp điểm). Chỉ Writing có CEFR; kỹ năng khác để NULL thay vì tự quy đổi điểm sang CEFR. CHECK `chk_skill_progress_skill_valid` giới hạn 4 giá trị `skill_name`. Đọc qua `GET /api/skills` (api-spec mục 7).
- **Môi trường Docker**: `docker-compose.yml` mount thêm `migrations/`, `tests/`, `alembic.ini`, `pytest.ini` vào container `api` nên `docker compose exec api alembic upgrade head` luôn dùng migration mới nhất trên máy, không cần rebuild image.
