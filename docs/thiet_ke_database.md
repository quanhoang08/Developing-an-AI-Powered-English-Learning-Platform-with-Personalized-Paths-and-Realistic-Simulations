# Thiết kế Database — Nền tảng học tiếng Anh ứng dụng AI

## 1. Nguyên tắc thiết kế

Thay vì tạo một nhóm bảng riêng cho từng tính năng (dẫn đến trùng lặp và khó mở rộng), schema được xây dựng quanh **6 nhóm thực thể lõi** mà phần lớn tính năng tái sử dụng, cộng thêm các bảng đặc thù cho phần logic khác biệt của từng tính năng:

| Nhóm lõi | Vai trò |
|---|---|
| `users` | Danh tính người học, cấu hình cá nhân |
| `documents` + `document_chunks` | Tài liệu người dùng tải lên + dữ liệu RAG (dùng chung cho Notebook, Podcast, Classic Mode, Writing...) |
| `learning_attempt` (khái niệm chung, cụ thể hóa theo từng bảng con) | Mọi lượt tương tác học đều gắn với 1 `user_id` + `document_id` (nullable nếu không gắn tài liệu) |
| `error_log` | Nơi tổng hợp lỗi từ **mọi** tính năng (ngữ pháp, phát âm, từ vựng, ý định giao tiếp...) — đây là bảng trung tâm nuôi thuật toán ưu tiên ôn tập, không phải bảng riêng của tính năng nào |
| `personas` / `accents` | Thư viện giọng nói hợp lệ dùng chung cho Podcast, AI Conversation Partner, TTS phản hồi |
| `review_priority_queue` | Hàng đợi ôn tập tổng hợp từ `vocab_reviews` + `error_log`, dùng chung cho Spaced Repetition và Dynamic Quiz Generator |

Việc đặt `error_log` và `review_priority_queue` làm bảng trung tâm (thay vì để mỗi tính năng tự lưu lỗi riêng) chính là điểm giúp tính năng "nhật ký lỗi xuyên suốt 4 kỹ năng" (USP cốt lõi của đề tài) hoạt động đúng — nếu không có tầng tổng hợp này, thuật toán ưu tiên ôn tập sẽ không thể nhìn xuyên suốt Đọc/Nghe/Viết/Nói.

## 2. Ánh xạ bảng theo mức ưu tiên (khớp mục 7.2 đề cương)

**Mức 1 (MVP):** `users`, `documents`, `notebook_folders`, `document_chunks`, `generated_passages`, `vocab_items`, `vocab_reviews`, `reading_sessions`, `reading_answers`, `contextual_guess_attempts`, `custom_stories`, `podcasts`, `transcript_segments`, `dictation_attempts`, `writing_submissions`, `writing_insights`, `rephrase_requests`, `error_log`, `review_priority_queue`, `quizzes`, `quiz_attempts`, `streaks`, `skill_progress`, `personas`.

**Mức 2:** `scenarios`, `conversation_sessions`, `conversation_turns`, `accents`, `movie_context_tts_fallback`, `movie_context_matches` (nhánh dự phòng — đọc mẫu bằng TTS, triển khai trước vì đơn giản, không phát sinh rủi ro nội dung).

**Mức 3:** `realtime_conversation_metrics` (mở rộng streaming cho Conversation Partner), `video_sources`, `video_subtitle_index` (nhánh tìm video thật — mục tiêu ưu tiên nhưng phức tạp hơn, triển khai sau nếu còn thời gian).

## 3. Vài quyết định thiết kế cần lưu ý khi trình bày trong khóa luận

- **`document_chunks.embedding`** dùng kiểu `vector(1536)` (khớp `text-embedding-3-small` của OpenAI) — nếu đổi model embedding khác, chiều vector phải đổi theo, nên đây là điểm cấu hình cần chốt sớm.
- **`conversation_turns`** lưu cả điểm phát âm, điểm ý định giao tiếp và điểm lịch sự trên **cùng một dòng** (turn), phản ánh đúng kiến trúc turn-based đã thống nhất — không tách thành 2 bảng Shadowing/Roleplay riêng như thiết kế cũ.
- **`realtime_conversation_metrics`** để trống ở Mức 1/2, chỉ kích hoạt khi nâng cấp lên streaming thời gian thực (Mức 3) — tách riêng để không phá vỡ schema Mức 2 khi mở rộng sau này.

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
| `ErrorJournalItem` có `spacedRepetitionLevel` ngay trên chính lỗi (không qua bảng SM-2 riêng như từ vựng) | Thêm cột `spaced_repetition_level` trực tiếp vào `error_log` — đơn giản hơn SM-2 đầy đủ, phù hợp vì lỗi ngữ pháp/phát âm không cần độ chính xác lịch ôn tập cao như từ vựng |

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

Sau khi đối chiếu toàn bộ mục 5.2/7.2/8 của đề cương với 33 bảng trong `schema.sql`, **không còn tính năng nào bị thiếu bảng lưu trữ tương ứng**. Các bảng còn lại (`writing_insights`, `skill_progress`, `error_log`, `review_priority_queue`...) đã được xác nhận khớp ở lần rà soát trước và không có thay đổi thêm. Điểm duy nhất cần bạn tiếp tục theo dõi là phần điểm ý định giao tiếp/lịch sự trong `conversation_turns` (đã nêu ở mục 4) — vẫn là phần thiết kế logic chưa được xác nhận bằng prototype.