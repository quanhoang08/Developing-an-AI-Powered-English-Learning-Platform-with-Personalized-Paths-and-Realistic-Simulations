# Feature Spec — Module 3: Viết (Writing)

> Nguồn đối chiếu: `de_cuong_khoa_luan.md` mục 5.2/9.6, `thiet_ke_database.md` mục 1/4.
> Bảng liên quan chính: `writing_submissions`, `writing_insights`, `rephrase_requests`, `documents`, `quiz_attempts`, `user_errors`.

---

## 1. Chọn đề bài & Viết luận — Summary / Extended Topic / Free Topic (Đầy đủ)

> ⚠️ **Lưu ý scope**: đề cương gốc (mục 5.2 `de_cuong_khoa_luan.md`) chỉ mô tả "Summary Essay" gắn với tài liệu đã tải lên. Phần mở rộng dưới đây (đề chủ đề mở rộng, đề tự chọn, gợi ý đề theo phong cách chứng chỉ) là **bổ sung ngoài phạm vi đã chốt trong đề cương** — cần cập nhật đồng bộ vào `de_cuong_khoa_luan.md` mục 5.2/10 nếu muốn giữ tính nhất quán tài liệu học thuật (nguyên tắc document-driven continuity, `lumina_context.md` mục 5). Để kiểm soát scope, thiết kế dưới đây **dùng chung 1 rubric chấm điểm** cho mọi loại đề không phải tóm tắt tài liệu — không xây riêng 3 hệ thống chấm cho TOEIC/IELTS/Cambridge.

### 1.0 Tổng quan
Đề bài viết luận có 3 nguồn, theo thứ tự ưu tiên gợi ý mặc định trên UI (không phải ràng buộc bắt buộc — người học luôn chọn được bất kỳ nguồn nào):

1. **Tóm tắt tài liệu đã học** (`document_summary`) — như thiết kế gốc, chấm theo mức độ bao phủ ý chính so với tài liệu.
2. **Chủ đề mở rộng liên quan** (`extended_topic`) — AI sinh 1 đề luận dạng ý kiến/thảo luận liên quan đến chủ đề của tài liệu đã học, không yêu cầu tóm tắt lại nội dung.
3. **Chủ đề tự chọn** (`free_topic`) — người học tự nhập đề, hoặc dùng gợi ý đề theo phong cách chứng chỉ quốc tế (TOEIC Writing, IELTS Writing Task 2, Cambridge English Writing).

### 1.1 Input

**Bước chọn đề** — `POST /api/writing/prompts/suggest`:
- `source_type` (bắt buộc: `document_summary` | `extended_topic` | `free_topic`)
- `document_id` (bắt buộc nếu `document_summary` hoặc `extended_topic`)
- `topic` (tuỳ chọn — chỉ dùng khi `free_topic` và người học tự nhập đề, không xin gợi ý)
- `certificate_style` (tuỳ chọn — chỉ dùng khi `free_topic` và xin gợi ý: `toeic` | `ielts` | `cambridge`)
- `level` (tuỳ chọn, mặc định `users.target_level`)

**Bước nộp bài** — `POST /api/writing/submissions/{submission_id}/submit`: `submitted_text` (bắt buộc, giữ nguyên như thiết kế gốc).

### 1.2 Flow

**Bước 1 — Chọn/sinh đề bài:**
1. `document_summary`: không cần sinh đề mới — `prompt_text` cố định theo template ("Tóm tắt nội dung chính của tài liệu"), ground truth lấy từ `document_chunks` (giữ nguyên flow gốc, chấm theo coverage — xem mục 1.3).
2. `extended_topic`:
   - Backend xác định chủ đề chính của `document_id` (từ `document_chunks`, qua LLM tóm tắt chủ đề 1 câu — có thể cache kết quả để không gọi lại LLM mỗi lần chọn đề trên cùng tài liệu).
   - Gọi Gemini sinh 1 đề luận dạng ý kiến/thảo luận liên quan đến chủ đề đó (ví dụ tài liệu về biến đổi khí hậu → đề "Do you think individual actions can make a real difference in fighting climate change? Discuss.").
   - **Không** dùng `document_chunks` làm ground truth chấm coverage cho loại đề này (đây không phải tóm tắt).
3. `free_topic` — 2 nhánh:
   - Người học tự nhập `topic` → `prompt_text` = chính topic đó, dùng thẳng, không qua LLM sinh đề.
   - Người học xin gợi ý (`certificate_style` + `level`, không truyền `topic`) → Gemini sinh 2-3 đề mẫu theo phong cách tương ứng (xem mục 1.4), trả về `prompt_options` để người học chọn 1 — **chưa tạo `writing_submissions`** ở bước này.
4. Sau khi có `prompt_text` cuối cùng (chọn trực tiếp hoặc chọn từ `prompt_options`), gọi `POST /api/writing/submissions` tạo `writing_submissions` (`source_type`, `prompt_text`, `document_id` nếu có, `certificate_style` nếu có), `submitted_text` để trống chờ nộp bài.

**Bước 2 — Nộp bài & chấm** (rubric khác nhau theo `source_type`):
- `document_summary`: chấm theo **coverage** ý chính (giữ nguyên thiết kế gốc — key points do LLM tự trích từ `document_chunks`, structured output, không so khớp câu chữ nguyên văn).
- `extended_topic` và `free_topic`: chấm theo **1 rubric chung**, 4 tiêu chí (mượn cấu trúc phổ biến IELTS Writing Task 2, áp dụng thống nhất bất kể phong cách đề):
  - Task Response — đề bài có được trả lời đầy đủ, đúng trọng tâm không.
  - Coherence & Cohesion — mạch lạc, liên kết ý.
  - Lexical Resource — vốn từ, đa dạng.
  - Grammatical Range & Accuracy — ngữ pháp.
- Cả 2 rubric đều trả về `cefr_level`/`ielts_band` ước tính + danh sách `writing_insights` (dùng chung bảng và cơ chế Inline Grammar Correction ở mục 2, không đổi).

### 1.3 Business rules
- **Cần bổ sung cột mới trên `writing_submissions`** (⚠️ ngoài phạm vi 5 file spec này — cần cập nhật `thiet_ke_database.md`/ERD riêng, không tự ý sửa ở đây):
  - `source_type` (enum: `document_summary` | `extended_topic` | `free_topic`)
  - `prompt_text` (text — lưu đề bài cụ thể để hiển thị lại và tái sử dụng)
  - `certificate_style` (nullable — chỉ set khi đề được sinh qua gợi ý chứng chỉ)
- Thứ tự ưu tiên 1-2-3 (mục 1.0) chỉ là **gợi ý mặc định trên UI** (ví dụ ưu tiên hiển thị "Tóm tắt tài liệu" nếu user đã có tài liệu `ready`) — không ép buộc, người học luôn chọn được `source_type` bất kỳ.
- `extended_topic` bắt buộc `document_id` hợp lệ (`status = 'ready'`) — nếu user chưa có tài liệu nào, `extended_topic` không khả dụng, trả lỗi nghiệp vụ `no_document_available`, gợi ý client chuyển hướng sang `free_topic`.
- Bài viết (mọi `source_type`) phải tối thiểu 30 từ mới được chấm (tránh spam/troll làm sai lệch dữ liệu Adaptive Learning Engine) — dưới ngưỡng trả lỗi nghiệp vụ `submission_too_short`, không lỗi hệ thống.
- **Không xây riêng 3 rubric khác nhau cho TOEIC/IELTS/Cambridge** — phong cách chứng chỉ chỉ ảnh hưởng bước **sinh đề** (độ dài, dạng câu hỏi, văn phong kỳ vọng), phần **chấm điểm** dùng chung 1 rubric 4 tiêu chí. Cần nêu rõ khi trình bày khóa luận: hệ thống mô phỏng *phong cách đề bài* của các chứng chỉ, không cam kết độ chính xác chấm điểm tương đương giám khảo chứng chỉ thật.

### 1.4 Đề xuất phân biệt phong cách đề theo chứng chỉ (khi sinh đề cho `free_topic`)
- `toeic`: đề ngắn, ngữ cảnh công sở/thương mại (email phản hồi, ý kiến về tình huống công việc), độ dài kỳ vọng ngắn hơn (~150-200 từ).
- `ielts`: đề dạng ý kiến/thảo luận/hai mặt vấn đề (agree-disagree, discuss both views, advantages-disadvantages), độ dài kỳ vọng ~250 từ, văn phong academic.
- `cambridge`: đề luận học thuật với chủ đề đa dạng (xã hội, giáo dục, môi trường...), văn phong trang trọng — hiểu theo hướng **Cambridge English Writing** (FCE/CAE). Nếu ý định ban đầu là dùng cấu trúc **đề Reading của Cambridge** làm nguồn cảm hứng chủ đề (khác với Writing), cần bạn xác nhận lại — hiện đề xuất đang hiểu là phong cách Writing để nhất quán với việc đây là bài tập viết luận.

### 1.5 Edge cases
- Tài liệu quá ngắn/chủ đề không đủ rõ ràng để mở rộng (`extended_topic`): backend vẫn cố sinh đề nhưng gắn cờ `topic_confidence_low`; client có thể cảnh báo nhẹ, không chặn hoàn toàn.
- Người học nhập `topic` tự do trùng lặp/không rõ nghĩa: không validate nội dung chủ đề ở bước chọn đề (chấp nhận mọi input hợp lệ về mặt kỹ thuật) — kiểm duyệt nội dung không phù hợp (nếu cần) áp dụng ở tầng chấm bài, không phải ở bước nhập đề.

### 1.6 Acceptance criteria
- [ ] `writing_submissions.source_type` luôn có giá trị hợp lệ trong 3 enum, không NULL.
- [ ] `document_summary` giữ nguyên hành vi/rubric như thiết kế gốc, không bị ảnh hưởng bởi phần mở rộng này (regression check).
- [ ] `extended_topic` và `free_topic` không bao giờ dùng `document_chunks` làm ground truth chấm coverage.
- [ ] Với `free_topic` qua gợi ý chứng chỉ, mỗi lần gọi trả về 2-3 đề khác nhau, không lặp lại y hệt đề của lần gọi trước trong cùng phiên.
- [ ] `writing_submissions.cefr_level`/`ielts_band` luôn có giá trị sau khi chấm xong (không NULL với submission đã `completed`), bất kể `source_type`.
- [ ] Bài dưới 30 từ bị từ chối với thông báo rõ ràng, không tạo `writing_submissions` rác, áp dụng cho cả 3 `source_type`.

---

## 2. Inline Grammar Correction (Đầy đủ)

### 2.1 Mục tiêu
Chấm và sửa lỗi ngữ pháp trực tiếp trong văn bản người học viết (không giới hạn ở Summary Essay — dùng chung cho mọi loại `writing_submissions`).

### 2.2 Input
- `submission_id` (bài viết đã tồn tại) hoặc `raw_text` (chấm nhanh không lưu — tuỳ chọn cho trường hợp preview trước khi nộp chính thức).

### 2.3 Flow
1. Gọi Gemini structured output, trả về danh sách lỗi dạng: `insight_type = 'grammar'`, `offset_start`, `offset_end` (vị trí trong text gốc), `original_text`, `suggested_text`, `explanation`.
2. Ghi từng lỗi vào `writing_insights` (đa hình theo `insight_type`, đúng thiết kế đã chốt ở `thiet_ke_database.md` mục 4 — cột `offset_start`/`offset_end` chỉ áp dụng cho `insight_type = 'grammar'`).
3. Đồng thời (piggyback — không gọi LLM riêng lần 2), phân loại lỗi để ghi vào `user_errors` phục vụ Adaptive Learning Engine — xem mục 3 (Rearrange the Block) về cơ chế piggyback.

### 2.4 Business rules
- `offset_start`/`offset_end` phải tính theo **ký tự** trên `submitted_text` gốc (UTF-8 code point, không phải byte) để client highlight đúng vị trí bất kể ngôn ngữ hiển thị.
- Mỗi lỗi ngữ pháp phát hiện qua Inline Correction, nếu đủ điều kiện phân loại rõ ràng, tự động tạo 1 dòng `user_errors` tương ứng (không cần hành động thêm từ người học) — đây chính là nguồn dữ liệu lỗi chính nuôi Adaptive Learning Engine từ Module Viết (mục 8 lộ trình, giai đoạn 3).

### 2.5 Acceptance criteria
- [ ] `offset_start`/`offset_end` của mọi `writing_insights` type `grammar` trỏ đúng vị trí lỗi trong `submitted_text` (không lệch do encoding).
- [ ] Mỗi lần chấm Inline Correction chỉ gọi LLM đúng 1 lần cho cả 2 mục đích (sửa lỗi hiển thị + ghi `user_errors`) — không phát sinh lệnh gọi riêng.

---

## 3. AI Rephrase — nâng cấp hành văn CEFR/IELTS (Đầy đủ)

### 3.1 Mục tiêu
Gợi ý viết lại cả câu theo hướng nâng cấp hành văn (khác `grammar` — đây là `insight_type = 'style'`, gợi ý viết lại toàn câu chứ không sửa lỗi cục bộ).

### 3.2 Input
- `submission_id` + `sentence_text` (câu cụ thể người học muốn nâng cấp) **hoặc** để trống `sentence_text` để hệ thống tự chọn câu yếu nhất trong bài.

### 3.3 Flow
1. Gọi Gemini sinh 1-2 phương án viết lại câu, kèm giải thích ngắn vì sao phương án đó tốt hơn (từ vựng phong phú hơn / cấu trúc câu đa dạng hơn / phù hợp văn phong academic hơn).
2. Ghi `rephrase_requests` (`submission_id`, `original_sentence`, `suggested_sentences` — JSONB mảng).

### 3.4 Business rules
- Rephrase **không** tự động ghi `user_errors` — đây là gợi ý nâng cao văn phong, không phải "lỗi sai" theo nghĩa nghiêm ngặt, tránh làm nhiễu Adaptive Learning Engine với dữ liệu không phải lỗi thật.

### 3.5 Acceptance criteria
- [ ] Mỗi `rephrase_requests` có ít nhất 1 phương án thay thế, kèm giải thích không rỗng.
- [ ] Không có `user_errors` nào được tạo từ luồng Rephrase.

---

## 4. Rearrange the Block — nhánh Writing/Grammar (Thử nghiệm giới hạn)

> Đây là nửa còn lại của subsystem chung mô tả ở `feature-reading.md` mục 6. Phần này chỉ mô tả điểm **khác biệt** so với nhánh Reading — đọc mục 6 bên đó trước.

### 4.1 Mục tiêu
Tương tự nhánh Reading, nhưng nội dung là câu/cụm từ ngữ pháp (ví dụ: sắp xếp lại thành phần câu đúng trật tự ngữ pháp tiếng Anh), không phải đoạn văn đọc hiểu.

### 4.2 Điểm khác biệt so với nhánh Reading

| Khía cạnh | Reading | Writing |
|---|---|---|
| Đơn vị khối | Câu/đoạn trong bài đọc | Cụm từ/thành phần câu (chunk ngữ pháp) |
| Nguồn lỗi ưu tiên | `user_errors` loại đọc hiểu | `user_errors` loại ngữ pháp (từ Inline Correction, mục 2) |
| Phân loại lỗi khi chấm | Rule-based diff (dạng đóng) | **Hybrid**: nếu bài tập có đúng 1 thứ tự chuẩn duy nhất → rule-based diff (dạng đóng); nếu chấp nhận nhiều thứ tự đúng ngữ pháp (dạng mở, ví dụ câu có thể đảo trạng ngữ mà vẫn đúng) → piggyback Gemini structured output trên lệnh gọi đánh giá Writing đã có sẵn ở mục 2 |

### 4.3 Business rules bổ sung
- Việc xác định 1 bài Rearrange Writing là "dạng đóng" hay "dạng mở" được quyết định **tại thời điểm sinh đề** (dựa vào độ phức tạp câu — câu đơn giản, ít khả năng đảo vị trí hợp lệ → dạng đóng; câu phức có trạng ngữ/mệnh đề phụ → dạng mở), lưu cờ `is_open_form` trên `quiz_attempts` để luồng chấm biết dùng nhánh nào mà không phải suy luận lại lúc chấm.

- **Triển khai thực tế (2026-09-24)** — khác thiết kế gốc ở 3 điểm, chốt sau khi đo với model thật:
  1. **Chấm bằng Ollama (local) cho MỌI bài chưa đạt 100%** (Reading lẫn Writing, dạng đóng lẫn mở), thay cho "piggyback Gemini" — không có lệnh gọi đánh giá Writing nào để dùng chung, và người dùng muốn dùng Ollama (không tốn quota Gemini). Đạt 100% theo luật thì không gọi LLM.
  2. **Kỹ thuật chấm "sắp lại rồi so khớp", KHÔNG hỏi "đúng hay sai?"**: đo trên 15 ca có nhãn cho thấy qwen2.5-7b / llama3.1-8b / mistral-7b đều dễ dãi (chỉ 8–11/15 đúng, chấm cả câu vô nghĩa "books in she often reads the library" là đúng). Nên `llm_service.judge_rearranged_order` đưa các khối theo thứ tự người học và bắt model sắp lại cho tự nhiên; chỉ khi model giữ nguyên đúng thứ tự đó mới nâng điểm lên 1.0. Đo lại ở mức cụm (đúng cách dùng thật): **0 lần chấm nhầm câu sai thành đúng**, nhưng ~3/6 thứ tự hợp lệ bị từ chối oan (model có xu hướng "chuẩn hóa" về câu gốc) → người học vẫn nhận điểm từng phần. Ollama lỗi thì lùi về điểm luật; response có `graded_by` (`rules`/`ollama`) + `explanation`.
  3. **`alternative_orders` do model sinh chỉ là gợi ý cờ `is_open_form`, KHÔNG được luật tự chấp nhận** — output thật gồm cả thứ tự vô nghĩa ("I usually a walk go for in the morning"). Thứ tự chấp nhận duy nhất theo luật là thứ tự gốc.
  Điểm thang 0–1. Migration `20260924_0014` cho phép `quiz_attempts.quiz_id` NULL và thêm `attempt_type`/`is_open_form`/`payload`. Kiểm tra khối do model sinh so theo chữ (bỏ hoa/thường + dấu câu) vì model 7B hay bỏ dấu chấm cuối câu; output hỏng được thử lại tối đa 3 lần trước khi báo lỗi cho người dùng.

### 4.4 Acceptance criteria
- [ ] Bài tập dạng đóng không gọi LLM khi chấm (giống Reading).
- [ ] Bài tập dạng mở chấm qua Gemini structured output **dùng chung lệnh gọi** với đánh giá Writing hiện có (không phát sinh API call LLM riêng biệt cho việc chấm Rearrange).
- [ ] `quiz_attempts.is_open_form` được set nhất quán tại thời điểm sinh đề, không đổi giá trị sau đó.

---

## 5. Ghi chú triển khai chung Module 3
- Toàn bộ endpoint yêu cầu JWT hợp lệ.
- `writing_insights` là bảng đa hình — service tầng Writing chịu trách nhiệm validate đúng tập cột theo từng `insight_type`, tránh để cột không liên quan bị set (ví dụ `offset_start` không nên có giá trị với `insight_type = 'style'`).
