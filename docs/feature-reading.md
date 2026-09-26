# Feature Spec — Module 1: Đọc & Từ vựng (Reading)

> Nguồn đối chiếu: `de_cuong_khoa_luan.md` mục 5.2/9.3, `thiet_ke_database.md` mục 1-2, `lumina_context.md` mục 3.1.
> Bảng liên quan chính: `documents`, `document_chunks`, `notebook_folders`, `generated_passages`, `reading_sessions`, `reading_answers`, `vocab_items`, `vocab_reviews`, `contextual_guess_attempts`, `custom_stories`, `quiz_attempts`, `user_errors`.

---

## 1. Classic Mode (Đầy đủ)

### 1.1 Mục tiêu
Người học đọc chính tài liệu họ tải lên (Notebook), trả lời câu hỏi trắc nghiệm được sinh từ nội dung, mỗi câu hỏi có trích dẫn đúng vị trí (chunk) trong tài liệu gốc.

### 1.2 Input
- `document_id` (bắt buộc, phải thuộc sở hữu user, `status = 'ready'` — đã chunk + embed xong).
- `num_questions` (tuỳ chọn, mặc định 5, giới hạn 3–15).
- `difficulty` (tuỳ chọn: `a2`/`b1`/`b2`/`c1`, mặc định lấy từ `users.target_level`).

### 1.3 Flow
1. Backend lấy top-N `document_chunks` của `document_id` (không cần truy vấn ngữ nghĩa — Classic Mode dùng tuần tự/đại diện toàn tài liệu, không phải trả lời câu hỏi tự do).
2. Gọi `llm_service` sinh bộ câu hỏi trắc nghiệm (structured output): mỗi câu hỏi gồm `question_text`, `options` (JSONB — 4 lựa chọn), `correct_option_index`, `source_chunk_id`.
3. Tạo `reading_sessions` (`document_id` set, `generated_passage_id = NULL`, `mode = 'classic'`).
4. Trả toàn bộ câu hỏi về client (không lộ `correct_option_index`).
5. Người học chọn đáp án từng câu → mỗi lần chọn ghi 1 dòng `reading_answers` (`options`, `correct_option_index`, `selected_option_index`, `source_chunk_id` copy lại để trích dẫn khi hiển thị kết quả).
6. Khi nộp toàn bộ, backend tính điểm, cập nhật `reading_sessions.score`, `completed_at`.

### 1.4 Business rules
- `document_id` phải thuộc `user_id` hiện tại (403 nếu không, không phải 404 — tránh lộ tồn tại tài liệu người khác thì trả 404 để không leak; **quyết định: trả 404** để nhất quán với nguyên tắc không lộ thông tin sở hữu).
- Không cho tạo session mới trên tài liệu chưa `status = 'ready'` → trả lỗi nghiệp vụ `document_not_ready`.
- Trích dẫn (`source_chunk_id`) bắt buộc phải tồn tại và thuộc đúng `document_id` — nếu LLM sinh câu hỏi không map được về chunk nào, loại câu hỏi đó khỏi kết quả (không trả câu hỏi thiếu trích dẫn).

### 1.5 Edge cases
- Tài liệu quá ngắn (ít hơn 3 chunk khả dụng): giảm `num_questions` tương ứng, không lỗi cứng.
- User nộp lại sau khi đã `completed_at`: từ chối (idempotent — trả lại session cũ, không tạo `reading_answers` trùng).

### 1.6 Acceptance criteria
- [ ] 100% câu hỏi trả về có `source_chunk_id` hợp lệ, trích dẫn đúng đoạn chứa đáp án.
- [ ] Điểm số tính đúng = số câu đúng / tổng câu, lưu đúng `reading_sessions.score`.
- [ ] Không thể xem `correct_option_index` trước khi nộp bài (kiểm tra ở response schema, không chỉ ở UI).
- [ ] Gọi lại API nộp bài 2 lần không tạo dữ liệu trùng.

---

## 2. Skim & Scan Challenge (Đầy đủ)

### 2.1 Mục tiêu
Luyện đọc lướt/quét thông tin có giới hạn thời gian. **Cập nhật (2026-09-16, theo yêu cầu người dùng)**: đoạn văn có 2 nguồn — trích **thật** từ tài liệu người học đã upload (Notebook), hoặc do AI sinh tự do theo chủ đề. Bản mô tả gốc ("do AI sinh mới... độc lập với Notebook") chỉ còn đúng cho nhánh `topic`; nhánh `document_id` là bổ sung mới. Câu hỏi trắc nghiệm luôn do Gemini sinh ở cả 2 nhánh — chỉ nguồn của **passage** khác nhau.

### 2.2 Input
Đúng 1 trong 2 (XOR, giống nguyên tắc `vocab_items.document_id`/`source_url`):
- `document_id` — passage là 1 chunk thật, chọn ngẫu nhiên từ `document_chunks` của tài liệu này (tài liệu phải thuộc user, `status = 'ready'`). Không paraphrase, không AI sinh lại nội dung.
- `topic` (chuỗi tự do, ví dụ "climate change") — passage do Gemini sinh mới.

Chung cho cả 2 nhánh:
- `level` (bắt buộc: `a2`/`b1`/`b2`/`c1`).
- `time_limit_seconds` (tuỳ chọn, mặc định 90).

### 2.3 Flow
1a. **Nhánh `document_id`**: lấy 1 `document_chunks` ngẫu nhiên của tài liệu → dùng nguyên văn làm `content`, không qua LLM. Lưu `generated_passages.source_document_id` để truy vết nguồn.
1b. **Nhánh `topic`**: gọi Gemini sinh đoạn văn mới (~150–300 từ tuỳ `level`) → lưu `generated_passages` (`topic`, `level`, `content`, `target_vocab_words`), `source_document_id = NULL`.
2. Gọi Gemini sinh câu hỏi trắc nghiệm trắc nghiệm bám `content` của passage (bất kể nguồn) — mỗi câu 4 lựa chọn, 1 đáp án đúng. **Không** còn trích dẫn offset/chunk nội bộ như bản thiết kế gốc (mục 2.3 bước 3 cũ) — do toàn bộ passage ngắn và hiển thị trọn vẹn cùng lúc, không cần citation theo câu như Classic Mode.
3. Tạo `reading_sessions` (`document_id = NULL`, `generated_passage_id` set, `mode = 'skim_scan'`) — dùng chung hạ tầng chấm điểm (`reading_answers`, endpoint submit) với Classic Mode.
4. Client hiển thị đếm ngược `time_limit_seconds`; hết giờ tự động nộp bài với các câu chưa trả lời tính là sai.

### 2.4 Business rules
- `reading_sessions` bắt buộc đúng 1 trong 2: `document_id` XOR `generated_passage_id` — enforce bằng `CHECK` constraint ở DB (đã có trong schema), API tầng service phải validate trước khi insert để trả lỗi rõ ràng thay vì để DB constraint văng lỗi 500.
- Request `document_id` XOR `topic` cũng validate ở schema layer (Pydantic), tương tự.
- Tài liệu dùng cho nhánh `document_id` phải `status = 'ready'` (đã ingest xong — xem `feature-notebook.md`); nếu chưa, trả lỗi nghiệp vụ `document_not_ready`.
- Gemini lỗi/quota hết (cả 2 nhánh, vì câu hỏi luôn cần AI) → trả lỗi AI có mã nguyên nhân (`{code, message, retryable}`: 503 `ollama_unreachable`/`ai_unavailable`, 504 `ollama_timeout`, 429 `ai_quota_exceeded`, 502 `ai_bad_output`), không để lộ traceback nội bộ.
- Hết thời gian: backend tự chấm dựa trên timestamp nhận được câu trả lời cuối cùng so với `reading_sessions.created_at`, không tin tưởng hoàn toàn đồng hồ client.

### 2.5 Acceptance criteria
- [ ] Nhánh `document_id`: `generated_passages.content` khớp nguyên văn 1 chunk thật trong `document_chunks`, không bị AI chỉnh sửa.
- [ ] Nhánh `topic`: đoạn văn sinh ra đúng độ dài/độ khó theo `level` yêu cầu (kiểm tra bằng review thủ công tập mẫu, không có threshold tự động).
- [ ] Nộp bài sau khi hết `time_limit_seconds` vẫn được chấp nhận nhưng câu chưa trả lời tính sai, không trả lỗi 4xx.
- [ ] Không có `reading_sessions` nào vi phạm ràng buộc XOR.
- [ ] Gemini lỗi trả `503` kèm `detail: {code, message, retryable}`, không phải lỗi 500 không rõ nguyên nhân.

---

## 3. Tra từ tương tác & Đoán nghĩa theo ngữ cảnh (Đầy đủ)

### 3.1 Mục tiêu
Người học bôi đen/chọn 1 từ trong bất kỳ nội dung đang đọc (Classic Mode, Skim & Scan, hoặc ngoài web qua Extension) → tra nghĩa nhanh, có thể lưu vào sổ từ vựng, và làm bài tập điền khuyết đoán nghĩa theo ngữ cảnh ngay sau đó.

### 3.2 Input — Tra từ
- `term` (bắt buộc).
- `context_sentence` (bắt buộc — câu chứa từ, để LLM định nghĩa đúng theo ngữ cảnh, không phải định nghĩa từ điển chung chung).
- `source_document_id` (tuỳ chọn, nullable).
- `source_url` (tuỳ chọn, nullable — dùng khi tra qua Extension).

### 3.3 Flow — Tra từ
1. Gọi `llm_service` lấy: định nghĩa theo ngữ cảnh, `synonyms`, `antonyms`, ví dụ câu khác.
2. Trả về client, **chưa lưu DB** (tra từ là hành động đọc/xem, không tự động ghi sổ).
3. Nếu người học bấm "Lưu vào sổ từ vựng" → tạo `vocab_items` (set đúng 1 trong `document_id` hoặc `source_url`, không set cả 2).

### 3.4 Input/Flow — Đoán nghĩa theo ngữ cảnh
1. Ngay sau khi tra 1 từ (đã lưu hoặc chưa), hệ thống có thể sinh 1 câu điền khuyết (`challenge_sentence`) chứa từ đó bị ẩn, kèm 4 lựa chọn nghĩa.
2. Ghi `contextual_guess_attempts` với `vocab_item_id` (nullable — nullable đúng như thiết kế đã chốt, vì từ có thể chưa được lưu), `term` (luôn set, không phụ thuộc `vocab_item_id`).
3. Người học chọn đáp án → ghi `selected_option_index`, so với `correct_option_index`.

### 3.5 Business rules
- `vocab_items`: đúng 1 trong `document_id` / `source_url` được set, còn lại NULL (không được cả hai cùng NULL và không được cả hai cùng có giá trị).
- Đoán nghĩa ngữ cảnh **không bắt buộc** phải theo sau tra từ — có thể sinh độc lập từ `vocab_items` đã lưu trước đó (ôn tập lại).

### 3.6 Acceptance criteria
- [ ] Tra cùng 1 từ trong 2 câu khác nhau trả về định nghĩa khác nhau nếu ngữ nghĩa theo ngữ cảnh khác nhau.
- [ ] `contextual_guess_attempts.term` luôn có giá trị kể cả khi `vocab_item_id` NULL.
- [ ] Không tồn tại `vocab_items` nào vi phạm ràng buộc "đúng 1 nguồn".

---

## 4. Sổ từ vựng — Spaced Repetition (SM-2) (Đầy đủ)

### 4.1 Mục tiêu
Ôn tập từ vựng đã lưu theo thuật toán SM-2 (SuperMemo-2 cổ điển), độc lập với `review_priority_queue` (vốn ưu tiên theo lỗi sai + độ mới, không phải riêng SM-2).

### 4.2 Input
- `GET /api/vocab/due`: không cần input ngoài JWT — trả danh sách `vocab_items` có `vocab_reviews.next_review_at <= now()`.
- `POST /api/vocab/{vocab_item_id}/review`: `quality` (0–5, thang đánh giá SM-2 chuẩn: 0 = quên hoàn toàn, 5 = nhớ hoàn hảo).

### 4.3 Flow
1. Lấy `vocab_reviews` hiện tại của `vocab_item_id` (quan hệ 1-1, `VOCAB_ITEMS ||--|| VOCAB_REVIEWS`).
2. Áp dụng công thức SM-2 chuẩn cập nhật `ease_factor`, khoảng lặp lại (interval), từ đó tính `next_review_at`.
3. Trả về `next_review_at` mới để client hiển thị lịch ôn tiếp theo.

### 4.4 Business rules
- `quality < 3`: reset interval về 1 ngày (theo đúng thuật toán SM-2 gốc — không tự sáng chế biến thể).
- `ease_factor` không được giảm dưới 1.3 (giới hạn chuẩn SM-2).

### 4.5 Acceptance criteria
- [ ] Kết quả `next_review_at`/`ease_factor` khớp công thức SM-2 tham chiếu trên tối thiểu 5 case test thủ công (quality 0, 2, 3, 4, 5 liên tiếp).
- [ ] Từ có `next_review_at` trong tương lai không xuất hiện trong `GET /api/vocab/due`.

---

## 5. AI Custom Story (Đầy đủ)

### 5.1 Mục tiêu
Sinh truyện ngắn theo yêu cầu, lồng ghép các từ vựng người học chọn để ôn lại trong ngữ cảnh mới.

### 5.2 Input
- `vocab_item_ids` (bắt buộc, danh sách từ 3–15 từ, phải thuộc user).
- `theme` (tuỳ chọn, chuỗi tự do).
- `length` (tuỳ chọn: `short` ~150 từ / `medium` ~300 từ, mặc định `short`).

### 5.3 Flow
1. Validate toàn bộ `vocab_item_ids` thuộc `user_id`.
2. Gọi Gemini sinh truyện đảm bảo dùng đủ toàn bộ từ trong danh sách (kiểm tra hậu-sinh bằng string match, không tin LLM tuyệt đối).
3. Nếu thiếu từ nào sau khi sinh → retry tối đa 1 lần với prompt nhấn mạnh từ còn thiếu; nếu vẫn thiếu, trả về kèm cảnh báo `missing_terms` chứ không lỗi cứng.
4. Lưu `custom_stories` (`vocab_item_ids`, `content`, `theme`).

### 5.4 Acceptance criteria
- [ ] Truyện sinh ra chứa ≥ 80% số từ yêu cầu ở lần gọi đầu tiên (đo trên tập mẫu thử nghiệm).
- [ ] Response luôn có field `missing_terms` (mảng rỗng nếu đủ từ) để client biết truyện có đạt yêu cầu không.

---

## 6. Rearrange the Block — nhánh Reading (Thử nghiệm giới hạn)

> Subsystem dùng chung với Writing (mục 3 trong `feature-writing.md`) và Adaptive Learning Engine — xem `error_tracking_service.py` trong `de_cuong_khoa_luan.md` mục 9.6.

### 6.1 Mục tiêu
Bài tập sắp xếp lại các khối câu/đoạn bị xáo trộn, ưu tiên lấy nội dung từ lỗi sai trong quá khứ của chính người học.

### 6.2 Input
- Không cần input từ client để khởi tạo — hệ thống tự chọn nguồn nội dung theo thứ tự ưu tiên (xem flow).
- `POST /api/reading/rearrange/{attempt_id}/submit`: `block_order` (mảng index thể hiện thứ tự người học sắp xếp).

### 6.3 Flow
1. **Chọn nguồn nội dung** (thứ tự ưu tiên, đã chốt trong `lumina_context.md` mục 3.1):
   a. Query `user_errors` của user, `error_type` thuộc nhóm liên quan Reading (xem Phụ lục enum ở `api-spec.md`), sắp theo `created_at DESC`, lấy lỗi gần nhất chưa được dùng làm bài Rearrange.
   b. Nếu không đủ dữ liệu lỗi (user mới hoặc lỗi loại hiếm) → fallback: lấy đoạn nội dung có sẵn (từ `document_chunks` hoặc `generated_passages` gần nhất user đã đọc) hoặc sinh mới qua Gemini.
2. Xáo trộn thứ tự khối (câu hoặc mệnh đề, tuỳ độ khó), tạo bản ghi `quiz_attempts` (loại `rearrange_reading`), trả về client.
3. Người học nộp `block_order` → chấm **partial credit theo tỷ lệ vị trí khối đặt đúng / tổng số khối** (đã chốt, không chấm nhị phân đúng/sai toàn bài).
4. Ghi kết quả vào `quiz_attempts` (điểm số), và nếu vẫn còn khối sai vị trí → ghi `user_errors` mới (`error_type` phù hợp, `spaced_repetition_level` khởi tạo mặc định).

### 6.4 Business rules — Phân loại lỗi hybrid (áp dụng chung Reading/Writing)
- **Bài tập dạng đóng** (đáp án thứ tự khối đã biết trước — đúng bản chất của Rearrange the Block): dùng **rule-based diff** so vị trí khối người học đặt với vị trí chuẩn. **Cập nhật 2026-09-24**: bài chưa đạt 100% theo luật được Ollama (local) xét thêm — nhiều đoạn văn có câu hoán đổi được — xem `feature-writing.md` mục 4.3 để biết kỹ thuật chấm và giới hạn đã đo. Đạt 100% theo luật thì không gọi LLM.
- Việc "piggyback Gemini structured output" (mục 3.1 context) áp dụng cho nhánh **Writing tự luận mở** (xem `feature-writing.md` mục 3), không áp dụng cho Reading vì Reading Rearrange luôn là dạng đóng.

### 6.5 Edge cases
- User không có `user_errors` nào phù hợp và cũng chưa đọc tài liệu nào → fallback cấp 2: sinh nội dung Rearrange hoàn toàn mới theo `target_level` mặc định của user.
- Một lỗi trong `user_errors` chỉ được dùng làm nguồn cho **tối đa 1 bài Rearrange đang mở** cùng lúc (tránh lặp lại quá dày) — đánh dấu bằng cờ nội bộ, không expose ra API response.

### 6.6 Acceptance criteria
- [ ] Điểm partial credit = (số khối đúng vị trí / tổng số khối), làm tròn theo quy ước chung của hệ thống (2 chữ số thập phân).
- [ ] Khi có ≥ 1 lỗi phù hợp trong `user_errors`, bài tập ưu tiên dùng lỗi đó thay vì fallback (kiểm tra qua test có seed data).
- [ ] Chỉ gọi Ollama khi điểm luật < 1.0 (đúng tuyệt đối thì không gọi LLM); Ollama lỗi thì lùi về điểm luật, không làm hỏng lượt nộp.

---

## 7. Ghi chú triển khai chung Module 1
- Toàn bộ endpoint Module 1 yêu cầu JWT hợp lệ (trừ không có endpoint public nào trong module này).
- Router không được gọi thẳng `llm_service`; luôn qua `reading_service.py` (nguyên tắc phân lớp, mục 9.1 đề cương).
- Xem `api-spec.md` để biết route/method/request-response mẫu chi tiết từng endpoint liệt kê ở trên.
