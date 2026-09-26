# Test Cases — Lumina Backend

> Nguồn đối chiếu: `feature-reading.md`, `feature-listening.md`, `feature-writing.md`, `feature-speaking.md`, `api-spec.md`. Mỗi test case bám theo acceptance criteria/business rules/edge cases đã chốt trong các file spec — không phát sinh case ngoài phạm vi đã thiết kế.
>
> Quy ước ID: `AUTH-xxx`, `DOC-xxx` (Notebook), `RD-xxx` (Reading), `LS-xxx` (Listening), `WR-xxx` (Writing), `SP-xxx` (Speaking), `AL-xxx` (Adaptive Learning Engine), `EXT-xxx` (Extension & Movie Context).
> Loại case: **HP** (Happy path) / **BR** (Business rule) / **EC** (Edge case) / **ERR** (Error/Auth/Ownership).

---

## 0. Test case dùng chung (áp dụng cho MỌI endpoint có auth)

> Không lặp lại ở từng module bên dưới — áp dụng ngầm định cho tất cả endpoint yêu cầu JWT (mục 0.2 `api-spec.md`), trừ khi ghi chú khác.

| ID | Loại | Kịch bản | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|
| COM-001 | ERR | Gọi endpoint yêu cầu auth mà không có JWT | Gửi request không kèm header `Authorization` | HTTP 401 |
| COM-002 | ERR | JWT hết hạn | Gửi request với access token đã hết hạn | HTTP 401, `error_code` ổn định (không lộ chi tiết stack trace) |
| COM-003 | ERR | JWT hợp lệ nhưng truy cập resource không thuộc sở hữu | User A gọi API thao tác trên resource thuộc User B (ví dụ `document_id` của B) | HTTP 404 (không phải 403 — tránh lộ thông tin tồn tại, đúng nguyên tắc mục 1.3 `feature-reading.md`) |
| COM-004 | ERR | Refresh token đã bị thu hồi/hết hạn | Gọi `POST /api/auth/refresh` với refresh token không hợp lệ | HTTP 401, không cấp access token mới |
| COM-005 | EC | Pagination vượt giới hạn | Gọi danh sách với `limit=500` | Backend tự giới hạn về `limit=100` (mục 0.4 `api-spec.md`), không lỗi 4xx |
| COM-006 | EC | Pagination `offset` vượt quá tổng số bản ghi | Gọi với `offset` lớn hơn `total` | Trả `items: []`, không lỗi |
| COM-007 | BR | `user_id` cố truyền qua body/query bị bỏ qua | Gửi `user_id` khác trong body của 1 request tạo resource | Backend resolve `user_id` từ JWT, bỏ qua giá trị trong body — resource tạo ra thuộc đúng người gọi request |

---

## 1. Auth & Users

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| AUTH-001 | HP | Đăng ký tài khoản mới | Email chưa tồn tại | `POST /api/auth/register` với email/password/target_level hợp lệ | HTTP 201, trả `user_id`, `email`; password được hash (bcrypt), không lưu plaintext |
| AUTH-002 | BR | Đăng ký với email đã tồn tại | Email đã có trong hệ thống | `POST /api/auth/register` với email trùng | HTTP 400, `error_code` rõ ràng (ví dụ `email_already_registered`) |
| AUTH-003 | HP | Đăng nhập thành công | Tài khoản tồn tại, đúng mật khẩu | `POST /api/auth/login` | HTTP 200, trả `access_token` + `refresh_token`, `token_type: "bearer"` |
| AUTH-004 | ERR | Đăng nhập sai mật khẩu | Tài khoản tồn tại | `POST /api/auth/login` với password sai | HTTP 401, không tiết lộ email có tồn tại hay không (thông báo chung chung) |
| AUTH-005 | HP | Refresh token hợp lệ | Đã login, có refresh token còn hạn | `POST /api/auth/refresh` | HTTP 200, cấp access token mới (và refresh token mới nếu áp dụng rotation) |
| AUTH-006 | HP | Extension đổi link code lấy token pair | Đã có `link_code` hợp lệ từ luồng "linking cookie" | `POST /api/auth/extension-token` | HTTP 200, trả token pair riêng, `refresh_tokens.client_type = 'extension'` |
| AUTH-007 | BR | Extension token dùng để gọi API ngoài phạm vi cho phép | Có token `client_type='extension'` | Gọi 1 endpoint web thông thường ngoài allow-list (không phải `/api/extension/*`, `/api/reading/lookup`, `/api/vocab`) — ví dụ `GET /api/documents` — bằng token này | **ĐÃ CHỐT (rà soát lần 3, xem `api-spec.md` mục 0.2 + mục 8, `docs/schema.sql` comment tại `refresh_tokens`)**: HTTP 403, `error_code: extension_token_scope_denied`. Enforce qua middleware đọc `client_type` — **đã code 2026-09-25**, test tự động: `tests/test_extension_scope.py` (DB-free + `*_integration`; migration `20260925_0017` đã áp, 14/14 pass 2026-09-26). Lưu ý: `/api/vocab` khớp đúng đường dẫn, không gồm `/api/vocab/*` |
| AUTH-007b | HP | Extension token gọi đúng route trong allow-list | Có token `client_type='extension'` | Gọi `POST /api/reading/lookup` hoặc `POST /api/vocab` bằng token này (không qua `/api/extension/lookup`) | HTTP 200, xử lý bình thường như token web — 2 route này nằm trong allow-list đã chốt, không bị từ chối |
| AUTH-008 | HP | Lấy thông tin user hiện tại | Đã login | `GET /api/users/me` | Trả đúng `id`, `email`, `target_level`, `created_at` của chính user gọi request |
| AUTH-009 | HP | Cập nhật `target_level` | Đã login | `PATCH /api/users/me` với `target_level` mới | Trả user object đã cập nhật, các lần gọi API sinh nội dung sau đó dùng `target_level` mới làm mặc định |

---

## 2. Notebook (Documents)

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| DOC-001 | HP | Upload tài liệu audio hợp lệ | Đã login | `POST /api/documents` multipart, file `.mp3`/`.wav` | HTTP 201, `status: "processing"` |
| DOC-002 | HP | Upload tài liệu .docx hợp lệ | Đã login | `POST /api/documents` multipart, file `.docx` | HTTP 201, `status: "processing"` |
| DOC-003 | BR | Upload định dạng không được hỗ trợ | Đã login | `POST /api/documents` với file `.pdf` hoặc `.jpg` | HTTP 400, `error_code` rõ ràng (ví dụ `unsupported_file_type`) — đúng giới hạn nghiêm ngặt "chỉ audio và .docx" (`lumina_context.md` mục 2) |
| DOC-004 | EC | Document đang `processing`, dùng để tạo bài Reading/Podcast/Writing | Tài liệu vừa upload, chưa `ready` | Gọi `POST /api/reading/classic/sessions` với `document_id` này | HTTP 400, `error_code: document_not_ready` (mục 1.3 `feature-reading.md`) |
| DOC-005 | HP | Document xử lý xong | — | Poll `GET /api/documents/{id}` đến khi `status = 'ready'` | Tài liệu sẵn sàng dùng cho mọi tính năng phụ thuộc |
| DOC-006 | EC | Document xử lý lỗi | Tài liệu upload nhưng backend xử lý thất bại (ví dụ audio hỏng) | Poll `GET /api/documents/{id}` | `status: "failed"`, không rơi vào trạng thái `processing` vô thời hạn |
| DOC-007 | HP | Tạo folder và gán tài liệu vào folder | Đã login | `POST /api/notebook-folders`, sau đó `PATCH /api/documents/{id}` với `folder_id` | Tài liệu xuất hiện khi lọc `GET /api/documents?folder_id=...` |
| DOC-008 | HP | Đánh dấu sao tài liệu | Tài liệu đã `ready` | `PATCH /api/documents/{id}` với `starred: true` | `GET /api/documents?starred=true` trả về đúng tài liệu này |
| DOC-009 | ERR | Xoá tài liệu không thuộc sở hữu | User B thử xoá document của User A | `DELETE /api/documents/{id}` (id của A) bằng token của B | HTTP 404 (theo COM-003) |
| DOC-010 | HP | Xoá tài liệu thành công | Tài liệu thuộc chính user | `DELETE /api/documents/{id}` | HTTP 204; các resource phụ thuộc (reading_sessions, podcasts...) xử lý theo cascade/orphan rule đã định nghĩa ở schema (cần đối chiếu `thiet_ke_database.md` nếu có ràng buộc FK ON DELETE cụ thể) |

---

## 3. Module 1 — Reading

### 3.1 Classic Mode

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| RD-001 | HP | Tạo session Classic Mode và làm bài đầy đủ | Document `ready` | `POST /api/reading/classic/sessions`, trả lời hết câu hỏi, `POST .../submit` | Điểm số = số câu đúng / tổng câu; mọi câu hỏi có `source_chunk_id` hợp lệ (mục 1.6 `feature-reading.md`) |
| RD-002 | BR | Không lộ đáp án trước khi nộp | Session vừa tạo | Kiểm tra response `POST /api/reading/classic/sessions` | Response **không** chứa `correct_option_index` ở bất kỳ câu hỏi nào |
| RD-003 | BR | Câu hỏi thiếu trích dẫn hợp lệ bị loại | LLM sinh câu hỏi không map được về chunk nào (mock/giả lập) | Sinh session | Câu hỏi đó không xuất hiện trong response trả về client |
| RD-004 | EC | Tài liệu quá ngắn (< 3 chunk khả dụng) | Document chỉ có 1-2 chunk | `POST /api/reading/classic/sessions` với `num_questions=5` | Số câu hỏi trả về tự giảm tương ứng, không lỗi cứng |
| RD-005 | EC | Nộp bài 2 lần trên cùng 1 session | Session đã `completed_at` | Gọi lại `POST .../submit` lần 2 | Idempotent — trả lại kết quả session cũ, không tạo `reading_answers` trùng |
| RD-006 | ERR | Tạo session trên document chưa `ready` | Document `status = 'processing'` | `POST /api/reading/classic/sessions` | HTTP 400, `error_code: document_not_ready` |
| RD-007 | ERR | Tạo session trên document không thuộc sở hữu | Document thuộc User khác | `POST /api/reading/classic/sessions` với `document_id` đó | HTTP 404 |

### 3.2 Skim & Scan Challenge

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| RD-008 | HP | Sinh đoạn văn mới và làm bài trong thời gian quy định | — | `POST /api/reading/skim-scan/sessions` với `topic`, `level`, nộp bài trước khi hết giờ | Điểm chấm bình thường; đoạn văn đúng độ dài/độ khó theo `level` (kiểm review thủ công) |
| RD-009 | EC | Hết thời gian mới nộp bài | Session đã tạo, `time_limit_seconds` đã trôi qua | Nộp bài sau khi hết giờ (client tự tính hoặc submit trễ) | Backend vẫn chấp nhận nộp (không trả lỗi 4xx); câu chưa trả lời tính sai; backend tự đối chiếu timestamp thay vì tin đồng hồ client |
| RD-010 | BR | `reading_sessions` không được set cả `document_id` lẫn `generated_passage_id` | Tạo session Skim & Scan | Kiểm tra bản ghi DB sau khi tạo | Đúng 1 trong 2 field có giá trị, field còn lại NULL (ràng buộc XOR) |
| RD-011 | BR | Validate ràng buộc XOR ở tầng service trước khi chạm DB | Request cố tình gửi thiếu cả topic (input sai) | Gửi request Skim & Scan thiếu `topic` | HTTP 422 (validate Pydantic), không rơi xuống tầng DB gây lỗi 500 |

### 3.3 Tra từ & Đoán nghĩa theo ngữ cảnh

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| RD-012 | HP | Tra 1 từ trong ngữ cảnh cụ thể | — | `POST /api/reading/lookup` với `term`, `context_sentence` | Trả định nghĩa, `synonyms`, `antonyms`; **không** tự động lưu vào `vocab_items` |
| RD-013 | BR | Cùng từ, khác câu ngữ cảnh → định nghĩa khác | Từ có nhiều nghĩa (ví dụ "bank") | Tra "bank" trong câu về tài chính, rồi tra lại trong câu về sông | 2 định nghĩa khác nhau, đúng theo ngữ cảnh từng câu |
| RD-014 | HP | Lưu từ vào sổ từ vựng sau khi tra | Đã tra 1 từ | `POST /api/vocab` với `document_id` hoặc `source_url` (đúng 1) | Tạo `vocab_items` thành công |
| RD-015 | BR | Lưu từ với cả `document_id` lẫn `source_url` cùng có giá trị | — | `POST /api/vocab` với cả 2 field cùng set | HTTP 400 — vi phạm ràng buộc "đúng 1 nguồn" |
| RD-016 | BR | Lưu từ thiếu cả `document_id` lẫn `source_url` | — | `POST /api/vocab` không set field nào | HTTP 400 |
| RD-017 | HP | Đoán nghĩa ngữ cảnh cho từ đã lưu | `vocab_item_id` tồn tại | `POST /api/reading/guess-context` với `vocab_item_id` | Trả `challenge_sentence` + `options`; `contextual_guess_attempts.vocab_item_id` set, `term` cũng set |
| RD-018 | EC | Đoán nghĩa ngữ cảnh cho từ **chưa lưu** | Từ vừa tra, chưa bấm lưu | `POST /api/reading/guess-context` chỉ với `term`, không có `vocab_item_id` | Vẫn sinh được challenge; `contextual_guess_attempts.vocab_item_id = NULL`, `term` vẫn có giá trị (mục 3.5 `feature-reading.md`) |
| RD-019 | ERR | Đoán nghĩa ngữ cảnh thiếu cả `vocab_item_id` lẫn `term` | — | `POST /api/reading/guess-context` không truyền gì | HTTP 422 |

### 3.4 Spaced Repetition (SM-2)

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| RD-020 | HP | Lấy danh sách từ đến hạn ôn | Có từ với `next_review_at <= now()` | `GET /api/vocab/due` | Trả đúng danh sách từ đến hạn, không có từ `next_review_at` ở tương lai |
| RD-021 | BR | Review với `quality = 5` (nhớ hoàn hảo) | Từ đã có `vocab_reviews` | `POST /api/vocab/{id}/review` với `quality: 5` | Interval tăng theo công thức SM-2 chuẩn, `next_review_at` dời xa hơn |
| RD-022 | BR | Review với `quality = 0` (quên hoàn toàn) | Từ đã có `vocab_reviews` với interval dài | `POST /api/vocab/{id}/review` với `quality: 0` | Interval reset về 1 ngày (đúng SM-2 gốc, mục 4.4 `feature-reading.md`) |
| RD-023 | BR | `ease_factor` không giảm dưới 1.3 | Nhiều lần review với `quality` thấp liên tiếp | Review lặp lại `quality: 0` hoặc `1` nhiều lần | `ease_factor` dừng ở 1.3, không giảm tiếp |
| RD-024 | EC | Test chuỗi 5 case liên tiếp (quality 0,2,3,4,5) | Từ mới, chưa review lần nào | Review tuần tự theo thứ tự trên | Kết quả từng bước khớp công thức SM-2 tham chiếu (mục 4.5 `feature-reading.md`) |

### 3.5 AI Custom Story

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| RD-025 | HP | Sinh truyện với 5 từ vựng | 5 `vocab_item_ids` hợp lệ, thuộc user | `POST /api/stories` | Truyện chứa đủ 5 từ; `missing_terms: []` |
| RD-026 | EC | LLM thiếu từ ở lần sinh đầu | Mock LLM trả truyện thiếu 1 từ | `POST /api/stories` | Backend tự retry 1 lần với prompt nhấn mạnh từ thiếu; nếu vẫn thiếu, trả `missing_terms` không rỗng thay vì lỗi cứng |
| RD-027 | ERR | `vocab_item_ids` chứa ID không thuộc user | 1 trong các ID thuộc user khác | `POST /api/stories` | HTTP 404 hoặc 400 (validate toàn bộ ID trước khi gọi LLM) |
| RD-028 | ERR | Số lượng từ ngoài khoảng 3–15 | — | `POST /api/stories` với 1 từ hoặc 20 từ | HTTP 422 |

### 3.6 Rearrange the Block — nhánh Reading

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| RD-029 | HP | Có lỗi phù hợp trong `user_errors` → dùng làm nguồn | User có `user_errors` loại đọc hiểu | `POST /api/reading/rearrange` | Nội dung bài tập lấy từ lỗi gần nhất, không rơi vào fallback |
| RD-030 | EC | Không có lỗi phù hợp, có tài liệu đã đọc → fallback cấp 1 | User chưa có `user_errors` loại đọc hiểu, đã đọc ≥1 tài liệu | `POST /api/reading/rearrange` | Nội dung lấy từ `document_chunks`/`generated_passages` gần nhất |
| RD-031 | EC | Không có lỗi, không có tài liệu → fallback cấp 2 | User mới hoàn toàn | `POST /api/reading/rearrange` | Sinh nội dung mới hoàn toàn theo `target_level` mặc định, không lỗi |
| RD-032 | HP | Chấm partial credit | Bài tập 5 khối, người học đặt đúng 3/5 vị trí | `POST .../submit` với `block_order` | `score = 3/5 = 0.60` (làm tròn 2 chữ số thập phân) |
| RD-033 | BR | Chỉ gọi Ollama khi điểm luật < 1.0 | Bài nộp đúng tuyệt đối / bài nộp lệch | Theo dõi lệnh gọi LLM khi chấm | Đúng tuyệt đối: 0 lệnh gọi, `graded_by = rules`. Lệch: đúng 1 lệnh gọi Ollama (`graded_by = ollama`); Ollama lỗi → điểm luật, HTTP 200 (mục 6.6 `feature-reading.md`) |
| RD-034 | BR | 1 lỗi trong `user_errors` không dùng cho 2 bài Rearrange đang mở cùng lúc | User vừa tạo 1 bài Rearrange từ lỗi X, chưa nộp | Tạo thêm 1 bài Rearrange mới | Bài mới không dùng lại lỗi X làm nguồn (trừ khi bài đầu đã đóng) |

---

## 4. Module 2 — Listening

### 4.1 Podcast tự động

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| LS-001 | HP | Tạo podcast từ tài liệu audio gốc | Document audio, `ready` | `POST /api/listening/podcasts` | `podcasts.audio_url` trỏ **đúng file audio gốc**, không phải file TTS mới (mục 1.6 `feature-listening.md`) |
| LS-002 | HP | Tạo podcast từ tài liệu .docx | Document .docx, `ready` | `POST /api/listening/podcasts` | Text được biên tập lại văn phong trước khi TTS; `audio_url` là file TTS mới sinh |
| LS-003 | EC | `persona_id` không hợp lệ/không active | — | `POST /api/listening/podcasts` với `persona_id` sai | Fallback về persona mặc định, không lỗi cứng |
| LS-004 | EC | Audio gốc quá dài, vượt giới hạn 1 lần gọi Azure STT | Audio > giới hạn xử lý | Tạo podcast | Audio được chia nhỏ, `transcript_segments` ghép lại liên tục theo `start_ms`, không có đoạn bị trùng/thiếu |
| LS-005 | BR | `transcript_segments` phủ toàn bộ độ dài audio | Podcast đã tạo xong | Kiểm tra tổng `end_ms` của segment cuối so với độ dài audio thực | Không có khoảng trống > 3 giây không giải thích được |

### 4.2 Transcript tương tác đồng bộ

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| LS-006 | HP | Lấy transcript đã sắp xếp | Podcast đã `ready` | `GET /api/listening/podcasts/{id}/transcript` | `transcript_segments` sắp theo `start_ms` tăng dần |
| LS-007 | HP | Click từ trong transcript để tra nghĩa | Đang xem transcript | Click 1 từ bất kỳ | Gọi được API tra từ (mục 3.2 `feature-reading.md`) với `context_sentence` đúng câu chứa từ, `source_document_id` = document gốc của podcast |
| LS-008 | EC | Độ lệch highlight so với audio thực tế | Đo thủ công trên tập mẫu | So sánh timestamp highlight với audio thực | Lệch < 300ms (mục 2.5 `feature-listening.md`) |

### 4.3 Dictation

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| LS-009 | HP | Nghe và gõ lại chính xác | Podcast `ready` | `POST /api/listening/dictation`, nghe, gõ đúng 100%, submit | `score` tối đa, không có lỗi nào ghi vào `user_errors` |
| LS-010 | HP | Gõ sai 1 số từ thông thường | — | Submit với vài từ sai chính tả (không phải từ hiếm) | Diff phát hiện đúng từ sai; `error_type = spelling` nếu ngữ âm gần, `listening_comprehension` nếu ngữ âm xa |
| LS-011 | BR | Không phân biệt hoa/thường và dấu câu thuần tuý | — | Gõ đúng nội dung nhưng khác hoa/thường, thiếu dấu phẩy | Không tính là lỗi |
| LS-012 | BR | Đồng nghĩa/viết tắt hợp lệ (don't vs do not) | Transcript gốc dùng "don't" | Gõ "do not" thay vì "don't" | Không tính là lỗi (qua bảng chuẩn hoá, không qua LLM) |
| LS-013 | EC | Bỏ trống hoàn toàn | — | Submit `transcribed_text = ""` | Toàn bộ từ trong đoạn tính là lỗi thiếu, không lỗi hệ thống |
| LS-014 | EC | Từ chuyên ngành/tên riêng, gõ sai nhưng ngữ âm gần đúng | Đoạn có từ được gắn nhãn `is_rare_or_proper: true` trong `reference_word_tags` | Gõ từ đó với chính tả gần đúng về âm | `error_type = vocabulary`, **không** phải `listening_comprehension`; feedback hiển thị "nghe đúng, chưa quen từ" (mục 3.5-3.6 `feature-listening.md`) |
| LS-015 | EC | Từ thông dụng, nghe nhầm rõ ràng (ngữ âm xa) | — | Gõ từ hoàn toàn khác về ngữ âm so với từ đúng | `error_type = listening_comprehension`, không bị ảnh hưởng bởi tầng phân loại mới |
| LS-016 | BR | Điểm số không đổi cách tính dù có tầng phân loại error_type mới | So sánh LS-010 và LS-014, cùng số từ sai | Submit cả 2 case | Cả 2 đều bị trừ điểm như nhau cho từ sai — chỉ khác `error_type` ghi vào `user_errors` |

---

## 5. Module 3 — Writing

### 5.1 Chọn đề bài & Viết luận — 3 nguồn (`document_summary` / `extended_topic` / `free_topic`)

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| WR-001 | HP | Tóm tắt tài liệu — luồng đầy đủ | Document `ready` | `POST /api/writing/prompts/suggest` (`source_type: document_summary`) → `POST /api/writing/submissions` → submit bài ≥30 từ | Chấm theo coverage; `cefr_level`/`ielts_band` có giá trị; `source_type` lưu đúng |
| WR-002 | HP | Chủ đề mở rộng — sinh đề liên quan tài liệu | Document `ready` | `POST /api/writing/prompts/suggest` (`source_type: extended_topic`) | Trả 1 `prompt_text` dạng ý kiến/thảo luận liên quan chủ đề tài liệu, không phải yêu cầu tóm tắt |
| WR-003 | HP | Chủ đề tự chọn — người dùng tự nhập | — | `POST /api/writing/prompts/suggest` (`source_type: free_topic`, `topic: "..."`) | `prompt_text` = chính topic nhập vào, không qua LLM sinh đề, không tạo submission ở bước này |
| WR-004 | HP | Chủ đề tự chọn — gợi ý theo phong cách chứng chỉ | — | `POST /api/writing/prompts/suggest` (`source_type: free_topic`, `certificate_style: ielts`) | Trả `prompt_options` (2-3 đề), **chưa** tạo `writing_submissions` |
| WR-005 | EC | Gọi gợi ý chứng chỉ 2 lần liên tiếp cùng phiên | Đã gọi 1 lần | Gọi lại `prompts/suggest` cùng `certificate_style`/`level` | 2-3 đề trả về khác với lần gọi trước (không lặp y hệt) |
| WR-006 | BR | `extended_topic` không dùng `document_chunks` chấm coverage | Bài `source_type = extended_topic` đã nộp | Kiểm tra logic chấm | Dùng rubric 4 tiêu chí (Task Response/Coherence/Lexical/Grammar), không có bước so coverage với `document_chunks` |
| WR-007 | BR | `free_topic` bắt buộc `document_id = NULL` | Tạo submission `source_type: free_topic` | Kiểm tra bản ghi DB | `document_id` luôn NULL |
| WR-008 | ERR | `extended_topic` khi user chưa có tài liệu nào | User mới, chưa upload tài liệu | `POST /api/writing/prompts/suggest` (`source_type: extended_topic`, không `document_id` hợp lệ) | HTTP 400, `error_code: no_document_available` |
| WR-009 | EC | Tài liệu chủ đề không đủ rõ ràng để mở rộng | Document quá ngắn/mơ hồ | `POST .../prompts/suggest` (`extended_topic`) | Vẫn sinh được `prompt_text`, kèm cờ `topic_confidence_low: true`, không lỗi cứng |
| WR-010 | BR | Bài dưới 30 từ bị từ chối (áp dụng cả 3 source_type) | — | Submit `submitted_text` < 30 từ cho từng loại `source_type` | HTTP 400, `error_code: submission_too_short`; không tạo `writing_submissions` rác |
| WR-011 | BR | `writing_submissions.source_type` luôn có giá trị hợp lệ | Tạo submission bất kỳ loại nào | Kiểm tra DB | `source_type` thuộc đúng 1 trong 3 enum, không NULL |
| WR-012 | EC | Regression: `document_summary` không bị ảnh hưởng bởi mở rộng | So sánh hành vi trước/sau khi thêm 2 loại đề mới | Chạy lại WR-001 | Kết quả giống hệt hành vi gốc (coverage-based), không lẫn rubric 4 tiêu chí |
| WR-012b | BR | `rubric_scores` chỉ có giá trị cho `extended_topic`/`free_topic` | Bài `document_summary` đã chấm xong | Kiểm tra response `POST .../submit` và bản ghi DB | `rubric_scores` là `NULL` khi `source_type = document_summary`; có giá trị (4 tiêu chí) khi `source_type` là `extended_topic`/`free_topic` — khớp `chk_writing_submissions_rubric` trong `docs/schema.sql` |

### 5.2 Inline Grammar Correction

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| WR-013 | HP | Chấm lỗi ngữ pháp trên bài đã lưu | Có `submission_id` | `POST /api/writing/grammar-check` với `submission_id` | Trả `writing_insights` type `grammar` với `offset_start`/`offset_end` đúng vị trí |
| WR-014 | HP | Chấm nhanh không lưu (`raw_text`) | — | `POST /api/writing/grammar-check` với `raw_text` | Trả kết quả tương tự, không cần `submission_id` trước |
| WR-015 | BR | Offset tính theo ký tự UTF-8, không lệch với văn bản có dấu tiếng Việt/ký tự đặc biệt | Bài viết chứa ký tự Unicode ngoài ASCII (ví dụ dấu ngoặc kép kiểu Anh " ") | Chạy grammar-check | `offset_start`/`offset_end` trỏ đúng vị trí lỗi, client highlight đúng |
| WR-016 | BR | Mỗi lỗi ngữ pháp tự động ghi `user_errors` | Bài có ≥1 lỗi ngữ pháp rõ ràng | Chạy grammar-check | Tạo tương ứng dòng `user_errors` với `error_type = grammar`, không cần hành động thêm từ user |
| WR-017 | BR | Không phát sinh lệnh gọi LLM riêng cho việc ghi `user_errors` | — | Theo dõi log số lệnh gọi LLM trong 1 lần grammar-check | Chỉ 1 lệnh gọi LLM duy nhất cho cả sửa lỗi hiển thị + ghi `user_errors` (piggyback) |

### 5.3 AI Rephrase

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| WR-018 | HP | Rephrase 1 câu cụ thể | Có `submission_id`, chọn 1 câu | `POST /api/writing/rephrase` với `sentence_text` | Trả ≥1 phương án thay thế kèm giải thích không rỗng |
| WR-019 | HP | Rephrase tự động chọn câu yếu nhất | Không truyền `sentence_text` | `POST /api/writing/rephrase` | Hệ thống tự chọn 1 câu trong bài, trả gợi ý tương tự |
| WR-020 | BR | Rephrase không ghi `user_errors` | Sau khi gọi rephrase | Kiểm tra `user_errors` | Không có bản ghi mới nào phát sinh từ luồng Rephrase |

### 5.4 Rearrange the Block — nhánh Writing

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| WR-021 | HP | Bài tập dạng đóng (câu đơn giản) | Câu nguồn đơn giản, 1 thứ tự chuẩn duy nhất | Sinh đề, `is_open_form = false` | Chấm rule-based diff, không gọi LLM |
| WR-022 | HP | Bài tập dạng mở (câu phức, nhiều thứ tự hợp lệ) | Câu nguồn có mệnh đề phụ/trạng ngữ | Sinh đề, `is_open_form = true` | Chấm qua Gemini structured output, **dùng chung** lệnh gọi với đánh giá Writing đã có (không phát sinh lệnh gọi LLM riêng biệt) |
| WR-023 | BR | Cờ `is_open_form` không đổi sau khi sinh đề | Bài đã tạo | Kiểm tra `quiz_attempts.is_open_form` trước và sau khi chấm | Giá trị nhất quán, không bị ghi đè trong quá trình chấm |

---

## 6. Module 4 — Speaking

### 6.1 Bạn đồng hành hội thoại AI — Turn-based

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| SP-001 | HP | 1 lượt hội thoại đầy đủ | Session đã tạo với `scenario_id` | `POST /api/speaking/sessions/{id}/turns` với audio hợp lệ | `conversation_turns` mới có đủ: `pronunciation_score`, `intent_score`, `politeness_score`, `response_text`; trả audio phản hồi (TTS) |
| SP-002 | BR | Nhánh B (Pronunciation Assessment) luôn nhận audio gốc, không qua STT text | — | Kiểm tra input thực tế gửi tới Azure Pronunciation Assessment | Audio gốc (PCM WAV 16kHz mono), không phải text đã transcribe |
| SP-003 | EC | Nhánh B lỗi/timeout nhưng nhánh A thành công | Mock Azure Pronunciation Assessment trả lỗi | Gửi 1 lượt nói | Vẫn trả `response_text` bình thường; `pronunciation_score = NULL`, cờ `pronunciation_assessment_failed = true`; không chặn toàn bộ lượt |
| SP-004 | EC | STT trả về text rỗng (audio không nghe rõ, sau khi cả 2 provider đã thử) | Audio im lặng/nhiễu | Gửi audio rỗng/nhiễu | HTTP 400, `error_code: empty_transcription`; **không** tạo `conversation_turns` |
| SP-004a | EC | Azure STT lỗi/timeout, fallback Whisper thành công | Mock Azure STT trả lỗi/timeout | Gửi 1 lượt nói bình thường | Retry Azure 1 lần → vẫn lỗi → tự động gọi Whisper lấy transcript → luồng tiếp tục bình thường; `conversation_turns.stt_provider_used = 'whisper'` |
| SP-004b | ERR | Cả Azure STT lẫn Whisper đều lỗi | Mock cả 2 provider trả lỗi | Gửi 1 lượt nói | HTTP 400 (hoặc 5xx tuỳ convention), `error_code: stt_service_unavailable`; **không** tạo `conversation_turns` |
| SP-004c | BR | Nhánh B (Pronunciation Assessment) không có fallback dù nhánh A đang dùng Whisper | Azure STT lỗi (dùng Whisper), Azure Pronunciation Assessment cũng lỗi trong cùng lượt | Gửi 1 lượt nói, mock cả Azure STT và Azure Pronunciation Assessment đều lỗi | Nhánh A fallback Whisper thành công, vẫn trả `response_text`; nhánh B **không** gọi Whisper — `pronunciation_score = NULL` + cờ `pronunciation_assessment_failed = true`, đúng thiết kế mục 1.4b `feature-speaking.md` |
| SP-004d | HP | Ghi nhận đúng provider khi Azure hoạt động bình thường | Azure STT hoạt động bình thường (không mock lỗi) | Gửi 1 lượt nói | `conversation_turns.stt_provider_used = 'azure'` |
| SP-005 | EC | Session không hoạt động > 30 phút | Session tạo > 30 phút trước, không có lượt nào gần đây | Gửi 1 lượt nói mới | Bị từ chối (session hết hạn), yêu cầu tạo session mới |
| SP-006 | BR | 1 session gắn đúng 1 `scenario_id` suốt vòng đời | Session đang mở | Thử gửi request đổi `scenario_id` giữa chừng (nếu API cho phép truyền) | Không có cách đổi scenario giữa session — phải tạo session mới |
| SP-007 | HP | Đo độ trễ phản hồi | — | Đo thời gian từ khi gửi audio đến khi nhận audio phản hồi | Thời gian được log lại phục vụ tiêu chí đánh giá độ trễ (mục 4 đề cương) |

### 6.2 Đề xuất — Logic điểm ý định giao tiếp & lịch sự

> ⚠️ Các case dưới đây kiểm tra theo **đề xuất** rubric ở `feature-speaking.md` mục 3 — cần chạy lại sau khi rubric được xác nhận chính thức.

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| SP-008 | HP | Phản hồi đạt đúng mục tiêu giao tiếp, đúng mức trang trọng | Scenario "đặt bàn nhà hàng" | Gửi câu trả lời rõ ràng, lịch sự phù hợp | `intent_score` 90-100, `politeness_score` 90-100 |
| SP-009 | EC | Phản hồi đạt mục tiêu nhưng văn phong quá trang trọng so với ngữ cảnh thân mật | Scenario "nói chuyện với bạn thân" | Trả lời bằng văn phong academic/khách sáo | `intent_score` cao (mục tiêu vẫn đạt) nhưng `politeness_score` bị trừ vì lệch mức trang trọng kỳ vọng (không tự nhiên) — đúng nguyên tắc "lịch sự không phải lúc nào cũng là trang trọng nhất" |
| SP-010 | EC | Phản hồi lạc đề so với tình huống | — | Trả lời không liên quan đến `scenario.goal` | `intent_score` 0-29 |
| SP-011 | ERR | LLM trả JSON không đúng schema | Mock LLM trả response sai định dạng | Gửi 1 lượt nói | Retry 1 lần; nếu vẫn lỗi, `intent_score`/`politeness_score` lưu NULL, log lại để review thủ công, không crash hệ thống |
| SP-012 | BR | `scenarios` thiếu cột `goal`/`formality_level` | Trước khi bổ sung cột (theo Phụ lục B `api-spec.md`) | Chạy luồng chấm điểm | Cần xác nhận: fail rõ ràng lúc migration/deploy thay vì chấm sai âm thầm — **case này phải fail có chủ đích cho đến khi schema được bổ sung** |

### 6.3 Daily Speaking & Slang — Sổ tay Phrasebook

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| SP-013 | HP | Lưu cụm từ có sẵn trong thư viện | `suggested_phrases` trả về gồm 1 cụm có `slang_phrase_id` | `POST /api/speaking/phrasebook` với `slang_phrase_id` | Tạo `user_phrasebook_entries` đúng, hiển thị lại đúng thông tin gốc khi truy vấn |
| SP-014 | HP | Lưu cụm từ LLM sinh tại chỗ (snapshot) | Cụm gợi ý không có `slang_phrase_id` | `POST /api/speaking/phrasebook` với `phrase_text`/`meaning`/`example_sentence` | Lưu snapshot đầy đủ, không phụ thuộc `slang_phrases` sau này có mục tương ứng hay không |
| SP-015 | ERR | Lưu thiếu cả `slang_phrase_id` lẫn `phrase_text` | — | `POST /api/speaking/phrasebook` không truyền field nào đủ | HTTP 400 — dữ liệu không đủ để hiển thị lại sau này |
| SP-016 | HP | Lọc sổ tay theo formality_level | Đã lưu nhiều cụm khác mức trang trọng | `GET /api/speaking/phrasebook?formality_level=casual` | Chỉ trả về cụm đúng mức lọc |

---

## 7. Module 0 — Adaptive Learning Engine

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| AL-001 | HP | Lấy danh sách lỗi, sắp theo ưu tiên | User có `user_errors` từ nhiều module (Reading, Writing, Listening, Speaking) | `GET /api/adaptive/errors` | Danh sách trả về xuyên suốt cả 4 kỹ năng, không chỉ 1 module — đúng USP "nhật ký lỗi xuyên suốt 4 kỹ năng" (`thiet_ke_database.md` mục 1) |
| AL-002 | HP | Lọc lỗi theo `error_type` | — | `GET /api/adaptive/errors?error_type=grammar` | Chỉ trả lỗi đúng loại được lọc |
| AL-003 | HP | Hàng đợi ôn tập tổng hợp | User có cả `vocab_reviews` đến hạn và `user_errors` chưa ôn | `GET /api/adaptive/review-queue` | Trả về tổng hợp từ cả 2 nguồn, không chỉ riêng vocab |
| AL-004 | HP | Sinh đề kiểm tra động theo điểm yếu | User có nhiều lỗi `error_type = grammar` | `POST /api/adaptive/quizzes/generate` với `focus_error_types: [grammar]` | Đề sinh ra tập trung vào loại lỗi được chỉ định |
| AL-005 | HP | Thống kê thói quen học tập | User có lịch sử hoạt động đa dạng | `GET /api/adaptive/habits` | Trả tần suất học, khung giờ, kỹ năng ưu tiên, tốc độ tiến bộ — đúng phạm vi MVP đã nâng tier (mục 3.4 `lumina_context.md`) |
| AL-006 | EC | User hoàn toàn mới, chưa có dữ liệu lỗi/hoạt động nào | User vừa đăng ký | Gọi cả 5 endpoint trên | Không lỗi 500; trả về danh sách/thống kê rỗng hợp lý (không crash vì thiếu dữ liệu) |
| AL-007 | HP | Streak — chuỗi ngày học liên tục | User học liên tục nhiều ngày | `GET /api/streaks` | `current_streak`/`longest_streak`/`last_active_date` chính xác |
| AL-008 | EC | Streak bị đứt (bỏ 1 ngày không học) | User có streak đang chạy, sau đó nghỉ 1 ngày | `GET /api/streaks` vào ngày kế tiếp sau khi nghỉ | `current_streak` reset về 0 hoặc 1 (tuỳ quy ước), `longest_streak` giữ nguyên giá trị cũ |

---

## 8. Module 5 — Browser Extension & Movie Delivery Context

### 8.1 Browser Extension

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| EXT-001 | HP | Luồng "linking cookie" đầy đủ | Đã login trên web | Login web → cookie set → extension đọc cookie qua `chrome.cookies` → `POST /api/auth/extension-token` | Nhận token pair riêng, `refresh_tokens.client_type = 'extension'` |
| EXT-002 | HP | Tra từ qua extension | Đã có extension token | `POST /api/extension/lookup` với `term`, `context_sentence`, `source_url` | Trả định nghĩa giống hệt luồng tra từ web (tái sử dụng `vocab_service`/`llm_service`, không luồng riêng) |
| EXT-003 | HP | Lưu từ tra qua extension | Đã tra 1 từ qua extension | `POST /api/vocab` với `source_url` (không có `document_id`) | Tạo `vocab_items` với `source_url` set đúng |
| EXT-004 | EC | Cookie linking hết hạn trước khi extension kịp đổi token | Cookie ngắn hạn đã hết hạn | Extension gọi `POST /api/auth/extension-token` trễ | HTTP 401, yêu cầu user login lại trên web để cookie mới được set |

### 8.2 Movie Delivery Context — nhánh TTS fallback (Thử nghiệm giới hạn)

> Chỉ nhánh `tts_fallback` được implement (theo quyết định mục 3.7 `lumina_context.md`). Nhánh `real_video` vẫn Định hướng mở rộng — không có test case triển khai thật cho nhánh này.

| ID | Loại | Kịch bản | Precondition | Bước thực hiện | Kết quả mong đợi |
|---|---|---|---|---|---|
| EXT-005 | HP | Tìm kiếm cụm từ, chỉ có kết quả TTS fallback | Chưa có nhánh video thật | `GET /api/movie-context/search?phrase=...` | Trả `matches` với `source_type: "tts_fallback"` — sinh câu ví dụ qua `llm_service`, đọc bằng `speech_service` TTS với giọng từ `personas` |
| EXT-006 | HP | Lưu 1 kết quả tìm được | Đã có `match_id` từ EXT-005 | `POST /api/movie-context/matches/{match_id}/save` | `movie_context_matches.is_saved = true` |
| EXT-007 | BR | Không phát sinh logic search/matching mới trong nhánh TTS fallback | — | Rà soát code implementation | Chỉ gọi `llm_service` (sinh câu ví dụ) + `speech_service` TTS — không có thuật toán tìm kiếm video nào được viết (đúng phạm vi đã chốt mục 3.7 `lumina_context.md`) |

---

## 9. Ghi chú khi thực thi bộ test case này

- Các case đánh dấu **ERR** liên quan sở hữu dữ liệu (COM-003 và tương đương ở từng module) nên được viết thành 1 bộ test tái sử dụng (fixture 2 user A/B) thay vì lặp lại thủ công cho từng resource.
- Các case phụ thuộc **đề xuất chưa được xác nhận chính thức** (SP-008 đến SP-012, WR liên quan `certificate_style`) cần gắn tag riêng (ví dụ `@pending-confirmation`) để dễ lọc ra khi rubric/enum được chốt lại — tránh báo cáo coverage sai lệch.
- AUTH-007/AUTH-007b (allow-list route cho token Extension) đã có middleware + test từ 2026-09-25; không còn cần tag `@pending-implementation` cho 2 case này. EXT-002 (`/api/extension/lookup`) đã có route + test (`test_extension_lookup_route_integration`). EXT-001/EXT-004 (linking cookie) vẫn chưa code.
- AL-006 (user hoàn toàn mới) nên chạy sớm trong bộ regression vì đây là nguồn gây lỗi 500 phổ biến nhất trong các hệ thống tổng hợp dữ liệu từ nhiều bảng.
- Toàn bộ case liên quan LLM (RD-025..027, WR-013..017, SP-001..012) nên có phiên bản chạy với **mock LLM response** (để test nhanh, ổn định, không phụ thuộc Gemini thật) và ít nhất 1 lần chạy với **LLM thật** trước khi demo/bảo vệ khóa luận.

---

## Phụ lục — Ví dụ cụ thể (dữ liệu thật thay cho mô tả trừu tượng)

> Chọn 6 test case tiêu biểu, khác loại (HP/BR/EC/ERR) và khác module, viết ra request/response JSON và số liệu tính toán thật — để dùng trực tiếp khi viết automated test hoặc test thủ công, không cần tự suy ra từ mô tả trong bảng.

### A. RD-024 (EC) — Chuỗi SM-2 review 5 bước liên tiếp

**Bối cảnh**: từ `serendipity` vừa được lưu vào sổ từ vựng, học viên review 5 lần liên tiếp với `quality` lần lượt: 0, 2, 3, 4, 5. Trạng thái ban đầu chuẩn SM-2: `ease_factor = 2.5`, `repetitions = 0`, `interval = 0`.

Kết quả tính thật theo công thức SM-2 gốc:

| Lần review | `quality` gửi lên | `ease_factor` sau | `repetitions` sau | `interval` sau (ngày) |
|---|---|---|---|---|
| 1 | 0 | 1.70 | 0 | 1 |
| 2 | 2 | 1.38 | 0 | 1 |
| 3 | 3 | 1.30 | 1 | 1 |
| 4 | 4 | 1.30 | 2 | 6 |
| 5 | 5 | 1.40 | 3 | 8 |

Request mẫu cho lần review thứ 4 (`quality = 4`):
```json
POST /api/vocab/a1b2c3d4-.../review
{ "quality": 4 }
```
Response mong đợi (đối chiếu đúng bảng trên):
```json
{
  "ease_factor": 1.3,
  "next_review_at": "2026-09-10T00:00:00Z"   // now + 6 ngày
}
```
**Điểm cần assert trong test**: ở lần 3, `ease_factor` tính ra 1.24 nhưng bị **clamp về 1.3** — đây chính là case dễ code sai nhất (quên áp giới hạn tối thiểu 1.3), nên bắt buộc có assertion riêng cho bước này.

---

### B. RD-032 (HP) — Chấm partial credit Rearrange the Block

**Bối cảnh**: bài tập 5 khối câu, thứ tự chuẩn là `[A, B, C, D, E]`. Học viên nộp thứ tự `[A, C, B, D, E]` — đúng vị trí 1, 4, 5 (A, D, E), sai vị trí 2 và 3 (B/C đổi chỗ nhau).

Request:
```json
POST /api/reading/rearrange/{attempt_id}/submit
{ "block_order": ["block_A", "block_C", "block_B", "block_D", "block_E"] }
```
Response mong đợi:
```json
{
  "score": 0.6,
  "correct_order": ["block_A", "block_B", "block_C", "block_D", "block_E"]
}
```
Tính toán: 3 khối đúng vị trí / 5 tổng khối = **0.60** (làm tròn 2 chữ số thập phân, đúng quy ước mục 0.4 chung của hệ thống).

---

### C. LS-014 (EC) — Phân biệt "nghe đúng, chưa biết từ" vs "nghe nhầm" bằng Metaphone

**Bối cảnh**: đoạn dictation có từ chuyên ngành `mitochondria`, đã được gắn nhãn `is_rare_or_proper: true` trong `reference_word_tags` lúc tạo bài.

**Case 1 — gõ gần đúng về âm** (nghe đúng, chưa biết mặt chữ):
```json
POST /api/listening/dictation/{attempt_id}/submit
{ "transcribed_text": "The mitocondria is the powerhouse of the cell." }
```
Tính thật: Metaphone("mitochondria") = `MTXNTR`, Metaphone("mitocondria") = `MTKNTR` → Levenshtein distance giữa 2 mã = **1** → dưới ngưỡng (≤1) → kết luận "ngữ âm gần".
```json
{
  "score": 0.83,   // ví dụ 5/6 từ đúng
  "errors": [
    { "type": "wrong", "word": "mitochondria", "position": 1, "error_type": "vocabulary" }
  ]
}
```

**Case 2 — nghe nhầm hẳn** (cùng từ, học viên gõ sai hoàn toàn về âm):
```json
{ "transcribed_text": "The microcondrea is the powerhouse of the cell." }
```
Tính thật: Metaphone("microcondrea") = `MKRKNTR` → Levenshtein distance so với `MTXNTR` = **3** → vượt ngưỡng → "ngữ âm xa".
```json
{
  "score": 0.83,
  "errors": [
    { "type": "wrong", "word": "mitochondria", "position": 1, "error_type": "listening_comprehension" }
  ]
}
```
**Điểm assert quan trọng**: `score` giống hệt nhau ở cả 2 case (đúng nguyên tắc "không đổi cách tính điểm") — chỉ `error_type` trong response khác nhau.

---

### D. WR-004 (HP) — Gợi ý đề bài theo phong cách chứng chỉ

Request:
```json
POST /api/writing/prompts/suggest
{ "source_type": "free_topic", "certificate_style": "ielts", "level": "b2" }
```
Response mẫu (2-3 đề, văn phong academic, ~250 từ, dạng agree-disagree/discuss-both-views đúng đặc trưng IELTS Writing Task 2 — mục 1.4 `feature-writing.md`):
```json
{
  "prompt_options": [
    {
      "prompt_text": "Some people believe that technology has made our lives more complicated, while others think it has made life easier. Discuss both views and give your own opinion."
    },
    {
      "prompt_text": "Many countries are investing heavily in renewable energy sources. To what extent do you agree or disagree that this is the best way to solve environmental problems?"
    }
  ]
}
```
So sánh với `toeic` cùng level (đề ngắn hơn, ngữ cảnh công sở — theo mục 1.4):
```json
POST /api/writing/prompts/suggest
{ "source_type": "free_topic", "certificate_style": "toeic", "level": "b2" }
```
```json
{
  "prompt_options": [
    {
      "prompt_text": "Your manager has asked you to write a short email proposing a change to the team's weekly meeting schedule. Explain your reasoning."
    }
  ]
}
```
**Điểm assert quan trọng**: 2 request chỉ khác `certificate_style`, kết quả phải khác nhau rõ rệt về độ dài/ngữ cảnh/văn phong — nếu 2 response giống nhau, rubric sinh đề chưa thực sự phân biệt phong cách.

---

### E. SP-009 (EC) — Ý định giao tiếp đạt nhưng lịch sự lệch ngữ cảnh

**Bối cảnh**: `scenario` = "Nói chuyện với bạn thân về việc rủ đi xem phim cuối tuần" (`formality_level: casual`).

Input (audio, transcribe ra text để minh hoạ):
> "I would be delighted if you could accompany me to the cinema this weekend, should your schedule permit."

Response mong đợi từ LLM (theo rubric đề xuất mục 3.1-3.2 `feature-speaking.md`):
```json
{
  "response_text": "Uhh sure, sounds fun! But you don't need to be so formal with me haha, we're friends!",
  "intent_score": 92,
  "intent_feedback": "Mục tiêu rủ đi xem phim được truyền đạt rõ ràng, đầy đủ thông tin.",
  "politeness_score": 55,
  "politeness_feedback": "Văn phong quá trang trọng so với ngữ cảnh nói chuyện với bạn thân — nghe không tự nhiên.",
  "suggested_phrases": [
    { "phrase": "Wanna catch a movie this weekend?", "meaning": "Rủ đi xem phim (thân mật, tự nhiên)", "source_note": "Cambridge English Corpus — informal spoken register" }
  ]
}
```
**Điểm assert quan trọng**: `intent_score` cao dù `politeness_score` thấp — 2 điểm số **độc lập nhau**, không được để 1 điểm thấp kéo điểm còn lại xuống theo (lỗi thường gặp nếu implement gộp chung logic).

---

### F. COM-003 (ERR) — Ownership check trả 404 thay vì 403

**Bối cảnh**: User A (`user_id: usr_aaa`) sở hữu document `doc_123`. User B (`user_id: usr_bbb`) đăng nhập bằng token riêng, cố truy cập document của A.

Request (dùng access token của **User B**):
```
DELETE /api/documents/doc_123
Authorization: Bearer <access_token_của_B>
```
Response mong đợi:
```json
HTTP 404 Not Found
{
  "error_code": "resource_not_found",
  "message": "Không tìm thấy tài liệu.",
  "details": null
}
```
**Điểm assert quan trọng**: **không phải** `403 Forbidden` — nếu trả 403, tức đã lộ thông tin "tài liệu này tồn tại nhưng bạn không có quyền", vi phạm nguyên tắc mục 1.3 `feature-reading.md`. Test case này nên chạy cho **mọi** resource sở hữu bởi user (documents, submissions, sessions...), không chỉ riêng Reading.
