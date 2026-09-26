# Feature Spec — Module Notebook: Knowledge Space & RAG Chat

> Nguồn đối chiếu: `de_cuong_khoa_luan.md`, `lumina_context.md` mục 3 (bổ sung 2026-09-16).
> Bảng liên quan chính: `documents`, `notebook_folders`, `document_chunks`, `notebook_chat_messages`.
> **File này là bổ sung mới** — Notebook trước đây chỉ có hợp đồng API trong `api-spec.md` mục 2, chưa có đặc tả flow/business rules riêng như 4 module kỹ năng. Được tạo cùng lúc với 2 tính năng ở mục 1 và 2 dưới đây.

---

## 1. Document Ingestion Pipeline (Đầy đủ, chỉ .docx)

### 1.1 Mục tiêu
Biến file `.docx` người dùng upload thành dữ liệu có thể tìm kiếm ngữ nghĩa (`document_chunks` + embedding), làm nền tảng cho Classic Mode (đã có trước), Skim & Scan nhánh `document_id`, Writing `document_summary`/`extended_topic`, và RAG Chat (mục 2 dưới đây).

### 1.2 Flow
1. `POST /api/documents` lưu file vào `storage/documents/`, tạo `documents` với `status = 'processing'`.
2. Ngay trong cùng request (đồng bộ — quy mô khóa luận chưa cần hàng đợi background job riêng):
   - Trích text bằng `python-docx` (`app/utils/text_extraction.py::extract_docx_text`).
   - Chia chunk theo ~350 từ/chunk, giữ nguyên thứ tự (`chunk_text`).
   - Với mỗi chunk: gọi Gemini Embedding (`models/gemini-embedding-001`, `output_dimensionality=768`, `task_type=RETRIEVAL_DOCUMENT`) → lưu `document_chunks.embedding` (`vector(768)`, pgvector).
   - Thành công toàn bộ → `documents.status = 'ready'`. Lỗi bất kỳ bước nào (file hỏng, Gemini lỗi...) → `status = 'failed'`, không rollback document (user thấy rõ trạng thái thay vì mất luôn record).
3. Response `POST /api/documents` trả `status` **sau khi** ingest xong (đồng bộ), không phải luôn `"processing"` như mô tả gốc ở `api-spec.md` mục 2 (file .docx nhỏ ingest xong trong vài giây nên trả thẳng `ready`/`failed`).

### 1.3 Business rules
- **Chỉ `.docx` có pipeline thật** ở phase này. Audio giữ nguyên `status = 'processing'` vĩnh viễn (không tự chuyển `ready`) vì chưa cấu hình `AZURE_SPEECH_KEY` thật — đây là scope của Module Listening, không phải thiếu sót ở đây. Khi Listening module build STT ingestion thật, cần bỏ giới hạn `rag_service.INGESTIBLE_EXTENSIONS = {".docx"}`.
- Embedding dùng `task_type` khác nhau cho document (`RETRIEVAL_DOCUMENT`, lúc ingest) và query (`RETRIEVAL_QUERY`, lúc chat/search) — đúng khuyến nghị của Gemini Embedding API để tối ưu độ chính xác retrieval.
- Lỗi Gemini (quota/network) trong lúc ingest **không** làm hỏng request upload — bắt exception, set `status = 'failed'`, vẫn trả `201`. Người dùng thấy tài liệu ở trạng thái lỗi thay vì upload bị treo/500.

### 1.4 Acceptance criteria
- [ ] Upload `.docx` hợp lệ → `document_chunks` có đúng số dòng bằng số chunk, mỗi dòng có `embedding` không NULL, `documents.status = 'ready'`.
- [ ] Upload `.docx` hỏng (không parse được) → `documents.status = 'failed'`, không có `document_chunks` nào được tạo, response vẫn `201` (không phải lỗi hệ thống).
- [ ] Upload audio → `status` giữ nguyên `'processing'`, không có `document_chunks`.

---

## 2. RAG Chat — hỏi đáp trên tài liệu kiểu NotebookLM (Đầy đủ)

### 2.1 Mục tiêu
Cho phép người học hỏi đáp tự do bằng ngôn ngữ tự nhiên về nội dung 1 tài liệu đã upload, câu trả lời **chỉ dựa trên nội dung tài liệu đó** (retrieval-augmented generation), kèm trích dẫn nguồn — tương tự trải nghiệm Google NotebookLM.

### 2.2 Input
- `document_id` (qua path `/api/documents/{document_id}/chat`) — phải thuộc user, `status = 'ready'`.
- `message` (bắt buộc, 1-4000 ký tự).

### 2.3 Flow
1. Lưu tin nhắn `role = 'user'` vào `notebook_chat_messages`.
2. Embed câu hỏi (`task_type=RETRIEVAL_QUERY`) → tìm top-5 `document_chunks` gần nghĩa nhất bằng cosine distance (`pgvector`, index `ivfflat`/`hnsw` có sẵn trên `document_chunks.embedding`).
3. Gọi Gemini sinh câu trả lời, prompt ép **chỉ dùng** các chunk tìm được + lịch sử 6 lượt hội thoại gần nhất; nếu chunk không đủ trả lời, mô hình phải nói rõ tài liệu không đề cập, không dùng kiến thức ngoài.
4. Lưu tin nhắn `role = 'assistant'` kèm `sources` (JSONB — danh sách `{chunk_id, excerpt}` của các chunk đã dùng).
5. Trả về cả 2 tin nhắn (`user_message`, `assistant_message`) cho client hiển thị ngay, không cần poll lại.

### 2.4 Business rules
- Ownership + `status = 'ready'` được kiểm tra trước khi cho chat — tài liệu đang `processing`/`failed` trả lỗi nghiệp vụ `document_not_ready`, không phải lỗi 500 do thiếu `document_chunks`.
- Lịch sử hội thoại (`GET .../chat`) sắp xếp theo `created_at` tăng dần, không giới hạn số lượng (khóa luận không cần phân trang cho quy mô demo).
- Gemini lỗi (quota/network) → lỗi AI có mã nguyên nhân (`{code, message, retryable}`: 503 `ollama_unreachable`/`ai_unavailable`, 504 `ollama_timeout`, 429 `ai_quota_exceeded`, 502 `ai_bad_output`); tin nhắn `user` **vẫn được lưu** (đã `flush` trước khi gọi LLM) nhưng không có `assistant_message` tương ứng — chấp nhận được vì user có thể thử lại, tránh mất câu hỏi đã gõ.
- Không dùng chung state với Classic Mode/Skim & Scan — đây là 1 subsystem độc lập (`notebook_chat_service.py`), không đụng tới `reading_sessions`.

### 2.5 Acceptance criteria
- [ ] Câu hỏi có đáp án nằm trong tài liệu → câu trả lời chứa đúng thông tin đó, `sources` không rỗng.
- [ ] Câu hỏi về nội dung KHÔNG có trong tài liệu → mô hình từ chối trả lời bằng kiến thức ngoài (kiểm tra thủ công qua review mẫu, không có test tự động cho "không bịa" vì bản chất LLM output không xác định 100%).
- [ ] `GET /api/documents/{id}/chat` sau khi chat phải thấy đủ các tin nhắn đã gửi, đúng thứ tự thời gian.
- [ ] Chat vào tài liệu của user khác → `404 document_not_found`, không lộ tài liệu tồn tại.
- [ ] Gemini lỗi → response `503` có `detail` rõ ràng, không phải kết nối bị reset (`Failed to fetch` phía client).

---

## 3. Tài liệu tham chiếu khác
- `api-spec.md` mục 2 (Notebook & RAG) — hợp đồng API đầy đủ 2 endpoint chat mới.
- `thiet_ke_database.md` — bảng `notebook_chat_messages` mới, cột `document_chunks.embedding`.
- `feature-reading.md` mục 2 — Skim & Scan nhánh `document_id` dùng chung pipeline ingestion ở mục 1 file này.
