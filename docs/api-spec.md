# API Spec — Lumina Backend (FastAPI)

> Đối chiếu với `feature-reading.md`, `feature-listening.md`, `feature-writing.md`, `feature-speaking.md` để biết business rules chi tiết từng endpoint. File này chỉ định nghĩa **hợp đồng API** (route, method, auth, request/response).

---

## 0. Quy ước chung

### 0.1 Base URL & versioning
- Base path: `/api` (chưa version hoá `/v1` — đề xuất giữ đơn giản cho phạm vi khóa luận, thêm version sau nếu cần).

### 0.2 Auth
- JWT Bearer (`Authorization: Bearer <access_token>`), phát hành qua `passlib[bcrypt]` + `python-jose`, cơ chế `OAuth2PasswordBearer` (mục 9.5 đề cương).
- Mọi endpoint yêu cầu auth trừ: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/refresh`, `POST /api/auth/extension-token`.
- Extension dùng cặp access/refresh token **riêng** (`client_type = 'extension'` trên `refresh_tokens`), không dùng chung token với web.
- **Phạm vi route của token Extension (ĐÃ CHỐT — rà soát lần 3, `docs/schema.sql` comment tại `refresh_tokens`, `lumina_context.md` mục 3.10)**: token `client_type='extension'` chỉ được chấp nhận trên `/api/extension/*`, `/api/reading/lookup` và `/api/vocab`; gọi bất kỳ route web nào khác bằng token này bị từ chối (`HTTP 403`, `error_code: extension_token_scope_denied` — xem AUTH-007 `test-cases (1).md`). Đây là allow-list **tĩnh**, không có cột riêng trong DB — enforce bằng middleware đọc `client_type` từ JWT claim. **Middleware đã code (2026-09-25, `app/core/extension_scope.py`)**: đọc claim `client_type` trong JWT; `/api/vocab` khớp **đúng** đường dẫn đó (không gồm `/api/vocab/*`). `POST /api/auth/login` nhận thêm `client_type` (`web` mặc định | `extension`); refresh giữ nguyên loại client. Cơ chế chính thức: extension đăng nhập bằng popup (`client_type: "extension"`); luồng linking cookie/`POST /api/auth/extension-token` bên dưới **không build** (quyết định 2026-09-26, lý do ở `lumina_context.md` mục 3.14). Migration `20260925_0017` (cột `refresh_tokens.client_type`) đã áp 2026-09-26.

### 0.3 Định dạng lỗi chuẩn
```json
{
  "error_code": "document_not_ready",
  "message": "Tài liệu chưa xử lý xong, vui lòng thử lại sau.",
  "details": null
}
```
- `error_code`: snake_case, ổn định (client có thể switch theo mã, không parse `message`).
- HTTP status: 400 (lỗi input/nghiệp vụ), 401 (chưa auth), 403 (không có quyền), 404 (không tồn tại/không thuộc sở hữu — dùng thay 403 khi cần tránh lộ thông tin tồn tại), 422 (lỗi validate Pydantic — FastAPI mặc định), 500 (lỗi hệ thống không lường trước).

### 0.4 Phân trang
- Danh sách dài dùng `limit`/`offset` query param, mặc định `limit=20`, tối đa `limit=100`.
- Response bọc: `{ "items": [...], "total": int, "limit": int, "offset": int }`.

### 0.5 Sở hữu dữ liệu
- Mọi resource gắn `user_id` chỉ truy vấn/sửa được bởi đúng chủ sở hữu, resolve từ JWT — không nhận `user_id` từ request body/query.

---

## 1. Auth & Users

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | `/api/auth/register` | Không | `{ email, password, target_level }` | `{ user_id, email }` |
| POST | `/api/auth/login` | Không | `{ email, password }` | `{ access_token, refresh_token, token_type: "bearer" }` |
| POST | `/api/auth/refresh` | Không (dùng refresh token) | `{ refresh_token }` | `{ access_token, refresh_token }` |
| POST | `/api/auth/extension-token` | Không (dùng `link_code`) | `{ link_code }` | `{ access_token, refresh_token }` (đánh dấu `client_type='extension'`) — **KHÔNG BUILD (quyết định 2026-09-26)**: extension đăng nhập bằng `POST /api/auth/login` với `client_type: "extension"` |
| GET | `/api/users/me` | JWT | — | `{ id, email, target_level, created_at }` |
| PATCH | `/api/users/me` | JWT | `{ target_level? }` | User object đầy đủ |

---

## 2. Notebook (Documents) & RAG

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | `/api/documents` | JWT | multipart: file (audio hoặc .docx), `folder_id?`, `tags?` | `{ id, status: "processing" }` |
| GET | `/api/documents` | JWT | query: `folder_id?`, `starred?`, `limit`, `offset` | Danh sách phân trang `documents` |
| GET | `/api/documents/{id}` | JWT | — | Document đầy đủ (404 nếu không thuộc user) |
| PATCH | `/api/documents/{id}` | JWT | `{ folder_id?, tags?, starred? }` | Document cập nhật |
| DELETE | `/api/documents/{id}` | JWT | — | 204 |
| POST | `/api/notebook-folders` | JWT | `{ name }` | `{ id, name }` |
| GET | `/api/notebook-folders` | JWT | — | Danh sách folder |
| GET | `/api/documents/{id}/chat` | JWT | — | `[{ id, role: "user"\|"assistant", content, sources: [{chunk_id, excerpt}]\|null, created_at }]` |
| POST | `/api/documents/{id}/chat` | JWT | `{ message }` | `{ user_message, assistant_message }` (cùng shape với item của GET ở trên) — RAG chat kiểu NotebookLM, xem `feature-notebook.md` mục 2 |

**Ràng buộc input**: chỉ nhận file audio hoặc `.docx` — mọi endpoint upload khác trong hệ thống (nếu có phát sinh sau này) phải tuân theo giới hạn này (mục 2 `lumina_context.md`).

**Trạng thái xử lý document** (`status`): `processing` → `ready` | `failed`. **Cập nhật (2026-09-16)**: với `.docx`, ingestion (extract + chunk + embed) chạy đồng bộ ngay trong `POST /api/documents` nên response đã trả `ready`/`failed` trực tiếp, không còn luôn là `processing` như mô tả gốc — client vẫn nên xử lý cả 3 trạng thái vì audio (chưa có pipeline thật) vẫn dừng ở `processing`. Xem `feature-notebook.md` mục 1.

**Chat yêu cầu `status = 'ready'`**: gọi chat khi tài liệu còn `processing`/`failed` trả `400 document_not_ready`.

---

## 3. Module 1 — Reading

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | `/api/reading/classic/sessions` | JWT | `{ document_id, num_questions?, difficulty? }` | `{ session_id, questions: [{ id, question_text, options }] }` (không có `correct_option_index`) |
| POST | `/api/reading/skim-scan/sessions` | JWT | `{ level, document_id?, topic?, time_limit_seconds? }` (đúng 1 trong `document_id`/`topic`) | `{ session_id, passage_id, title, content, source_document_id, questions, time_limit_seconds }` — `source_document_id` khác `null` khi passage trích từ tài liệu thật thay vì AI tự sinh (mục 2 `feature-reading.md`, cập nhật 2026-09-16) |
| POST | `/api/reading/sessions/{session_id}/submit` | JWT | `{ answers: [{ question_id, selected_option_index }] }` | `{ score, results: [{ question_id, correct_option_index, source_chunk_id }] }` |
| POST | `/api/reading/lookup` | JWT (web hoặc extension — xem mục 0.2) | `{ term, context_sentence, source_document_id?, source_url? }` | `{ definition, synonyms, antonyms }` |
| POST | `/api/reading/guess-context` | JWT | `{ vocab_item_id? , term? }` (ít nhất 1 trong 2) | `{ attempt_id, challenge_sentence, options }` |
| POST | `/api/reading/guess-context/{attempt_id}/submit` | JWT | `{ selected_option_index }` | `{ correct, correct_option_index }` |
| POST | `/api/vocab` | JWT (web hoặc extension — xem mục 0.2) | `{ term, definition, document_id? , source_url? }` (đúng 1 nguồn) | `vocab_items` object; `409 vocab_duplicate` nếu user đã lưu từ này (không phân biệt hoa/thường) |
| GET | `/api/vocab/due` | JWT | — | Danh sách `vocab_items` đến hạn ôn |
| POST | `/api/vocab/{id}/review` | JWT | `{ quality }` (0-5) | `{ next_review_at, ease_factor }` |
| POST | `/api/stories` | JWT | `{ vocab_item_ids, theme?, length? }` | `{ id, content, missing_terms }` |
| POST | `/api/reading/rearrange` | JWT | — (không cần input, hệ thống tự chọn nguồn) | `{ attempt_id, blocks: [{ id, text }] }` (thứ tự đã xáo trộn) |
| POST | `/api/reading/rearrange/{attempt_id}/submit` | JWT | `{ block_order: [uuid, ...] }` | `{ score, correct_order }` |

---

## 4. Module 2 — Listening

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | `/api/listening/podcasts` | JWT | `{ document_id, persona_id? }` | `{ id, status: "processing" }` |
| GET | `/api/listening/podcasts/{id}` | JWT | — | `{ id, audio_url, persona_id, status }` |
| GET | `/api/listening/podcasts/{id}/transcript` | JWT | — | `{ segments: [{ text, start_ms, end_ms }] }` |
| POST | `/api/listening/dictation` | JWT | `{ podcast_id, segment_range? }` | `{ attempt_id, audio_url }` (không trả text gốc) |
| POST | `/api/listening/dictation/{attempt_id}/submit` | JWT | `{ transcribed_text }` | `{ score, errors: [{ type: "missing"\|"extra"\|"wrong", word, position }] }` |

---

## 5. Module 3 — Writing

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | `/api/writing/prompts/suggest` | JWT | `{ source_type: "document_summary"\|"extended_topic"\|"free_topic", document_id?, topic?, certificate_style?, level? }` | Nếu `document_summary`/`extended_topic`/`free_topic`+`topic`: `{ prompt_text, source_type }`. Nếu `free_topic`+`certificate_style` (không `topic`): `{ prompt_options: [{ prompt_text }] }` (chưa tạo submission) |
| POST | `/api/writing/submissions` | JWT | `{ source_type, prompt_text, document_id?, certificate_style? }` | `{ submission_id, source_type, prompt_text }` |
| POST | `/api/writing/submissions/{submission_id}/submit` | JWT | `{ submitted_text }` | `{ score, cefr_level, ielts_band, source_type, rubric_scores, insights: [...] }` — `rubric_scores` (object `{task_response, coherence_cohesion, lexical_resource, grammatical_range_accuracy}`, thang 0-100) chỉ có giá trị khi `source_type` là `extended_topic`/`free_topic`; `NULL`/omitted khi `document_summary` (chấm theo coverage, không dùng rubric này — xem `docs/schema.sql` bảng `writing_submissions`) |
| POST | `/api/writing/grammar-check` | JWT | `{ submission_id? , raw_text? }` (1 trong 2) | `{ insights: [{ insight_type: "grammar", offset_start, offset_end, original_text, suggested_text, explanation }] }` |
| POST | `/api/writing/rephrase` | JWT | `{ submission_id, sentence_text? }` | `{ original_sentence, suggested_sentences: [{ text, explanation }] }` |
| POST | `/api/writing/rearrange` | JWT | — | `{ attempt_id, blocks, is_open_form }` |
| POST | `/api/writing/rearrange/{attempt_id}/submit` | JWT | `{ block_order }` | `{ score, correct_order }` |

---

## 6. Module 4 — Speaking

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/api/speaking/scenarios` | JWT | query: `formality_level?` | Danh sách `scenarios` |
| POST | `/api/speaking/sessions` | JWT | `{ scenario_id, persona_id? }` | `{ session_id }` |
| POST | `/api/speaking/sessions/{session_id}/turns` | JWT | multipart: audio file | `{ turn_id, response_text, response_audio_url, pronunciation_score, intent_score, politeness_score, intent_feedback, politeness_feedback, suggested_phrases, stt_provider_used }` |
| GET | `/api/speaking/sessions/{session_id}` | JWT | — | Session + toàn bộ `conversation_turns` |
| POST | `/api/speaking/phrasebook` | JWT | `{ slang_phrase_id?, conversation_turn_id?, phrase_text?, meaning?, example_sentence? }` | `user_phrasebook_entries` object |
| GET | `/api/speaking/phrasebook` | JWT | query: `formality_level?` | Danh sách đã lưu |

---

## 7. Module 0 — Adaptive Learning Engine

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/api/adaptive/errors` | JWT | query: `error_type?`, `limit`, `offset` | Danh sách `user_errors`, sắp theo mức ưu tiên |
| GET | `/api/adaptive/review-queue` | JWT | — | `review_priority_queue` hiện tại của user |
| POST | `/api/adaptive/quizzes/generate` | JWT | `{ focus_error_types?: [...], num_questions?: 1-10 (mặc định 5) }` | `201 { quiz_id, questions: [{ question_text, options, error_type }] }` (sinh động theo điểm yếu; **không** kèm đáp án đúng) |
| POST | `/api/adaptive/quizzes/{quiz_id}/attempts` | JWT | `{ answers: [int] }` (chỉ số đáp án, đúng thứ tự câu hỏi) | `{ attempt_id, score, results: [{ is_correct, correct_option_index, explanation }] }` |
| GET | `/api/adaptive/habits` | JWT | — | Thống kê thói quen học 30 ngày: `active_days`, `activities_per_active_day`, `peak_hour`, `activity_by_skill`, `preferred_skill`, `progress_trend`, `quiz_score_change` |

Ghi chú hành vi:
- `GET /api/adaptive/errors`: `limit` 1–100 (mặc định 20), `offset` ≥ 0; mỗi phần tử có `id`, `error_type`, `spaced_repetition_level`, `detail` (`{ source, original_text?, corrected_text?, explanation? }`), `created_at`, `priority_score`.
- `GET /api/adaptive/review-queue` tính lại hàng đợi mỗi lần gọi (top 50). `item_type` là `vocab` (từ đến hạn ôn SM-2) hoặc `error`; `label` là từ hoặc `error_type`.
- Mã lỗi quiz: `409 no_errors_to_practice` (chưa có lỗi nào), `422 invalid_error_type` / `answer_count_mismatch`, `404 quiz_not_found` (kể cả quiz của người khác), lỗi AI có mã nguyên nhân (`{code, message, retryable}`: 503 `ollama_unreachable`/`ai_unavailable`, 504 `ollama_timeout`, 429 `ai_quota_exceeded`, 502 `ai_bad_output`).
- Nộp bài: câu đúng tăng `spaced_repetition_level` của lỗi gốc (tối đa 5), câu sai ghi thêm 1 `user_errors` gắn `quiz_attempt_id`. XP (`quiz_completed`, 25) chỉ cộng ở lượt làm đầu tiên của mỗi đề.
- Nguồn ghi `user_errors`: Writing (insight `grammar`/`vocabulary`), Dictation, và câu trả lời sai trong quiz.
| GET | `/api/streaks` | JWT | — | `{ current_streak, longest_streak, last_active_date }` |
| GET | `/api/skills` | JWT | — | `[{ skill_name, score, cefr_level, updated_at }]` — chỉ kỹ năng đã có điểm (`reading`/`listening`/`writing`/`speaking`), thứ tự cố định; `score` là trung bình động thang 0-100; `cefr_level` chỉ có với `writing`. Rỗng với user chưa học |

---

## 8. Module 5 — Browser Extension & Movie Delivery Context

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | `/api/auth/extension-token` | Xem mục 1 | | |
| POST | `/api/extension/lookup` | JWT (extension token) | `{ term, context_sentence, source_url }` | Giống `/api/reading/lookup`, tái sử dụng `vocab_service`/`llm_service` (không luồng riêng, mục 9.5 đề cương) |
| GET | `/api/movie-context/search` | JWT | query: `phrase` | `{ matches: [{ match_id, source_type, phrase_text, is_saved, audio_url?, video_url?, title?, start_ms?, end_ms? }] }` — tìm phụ đề trong kho video demo trước (full-text `simple`, tối đa 3 dòng): khớp → `source_type: "real_video"` với `video_url`/`title`/`start_ms`/`end_ms` (`audio_url: null`); không khớp → nhánh TTS fallback (Thử nghiệm giới hạn) `source_type: "tts_fallback"` với `audio_url`. Kho video hiện chỉ là 3 cảnh mô phỏng (`scripts/seed_demo_videos.py`), chưa phải video thật. Thêm `GET /api/movie-context/matches/{id}/audio` và `.../video` (JWT, chỉ chủ sở hữu, 404 nếu không phải) |
| POST | `/api/movie-context/matches/{match_id}/save` | JWT | — | Đánh dấu `movie_context_matches.is_saved = true` |
| GET | `/api/movie-context/matches/{match_id}/subtitles` | JWT | — | `[{ text, start_ms, end_ms, is_match }]` — mọi dòng phụ đề của video chứa cảnh khớp, theo thời gian; `is_match = true` cho dòng chứa cụm người học tìm (frontend tô màu khác). Chỉ với match `real_video` của chính user, còn lại `404 movie_video_not_found` |

**Phạm vi route cho token Extension (nhắc lại từ mục 0.2)**: `/api/extension/lookup` ở trên là route dành riêng cho extension, nhưng allow-list đã chốt còn cho phép token extension gọi thẳng `/api/reading/lookup` và `/api/vocab` (không chỉ `/api/extension/*`) — hai route web này cũng trả kết quả hợp lệ khi gọi bằng token `client_type='extension'`. Middleware enforce allow-list này đã code — xem mục 0.2. `/api/extension/lookup` đã có route (2026-09-26, `routers/extension.py`): dùng lại đúng handler của `/api/reading/lookup` (cùng request/response, cùng `lookup_term`), extension gọi route này để tra từ trên mọi trang web.

---

## 9. Phụ lục A — ĐỀ XUẤT enum `error_type`

> Trạng thái: **chưa chốt chính thức** (theo `lumina_context.md` mục 4, điểm ưu tiên nhất). Đề xuất dưới đây bao phủ đúng các nguồn phát sinh lỗi đã mô tả trong 4 file feature spec — cần xác nhận trước khi viết migration Alembic cho `user_errors`.

```python
class ErrorType(str, Enum):
    GRAMMAR = "grammar"                          # Inline Grammar Correction (Writing), Rearrange Writing dạng đóng
    VOCABULARY = "vocabulary"                     # đoán nghĩa sai, dùng từ sai ngữ cảnh
    SPELLING = "spelling"                         # lỗi chính tả trong Dictation/Writing
    PRONUNCIATION = "pronunciation"                # Azure Pronunciation Assessment điểm thấp (Speaking)
    LISTENING_COMPREHENSION = "listening_comprehension"  # Dictation, câu hỏi nghe hiểu sai
    READING_COMPREHENSION = "reading_comprehension"       # Classic Mode/Skim & Scan trả lời sai
    WRITING_COHERENCE = "writing_coherence"        # lỗi mạch lạc/hành văn (không phải ngữ pháp thuần)
    COMMUNICATIVE_INTENT = "communicative_intent"  # intent_score thấp trong Speaking
    POLITENESS = "politeness"                      # politeness_score thấp trong Speaking
```

**Lý do đề xuất tách `GRAMMAR` khỏi `WRITING_COHERENCE`**: `insight_type='grammar'` (có offset cụ thể, sửa được máy móc) và lỗi mạch lạc/văn phong (không có vị trí offset rõ ràng, mang tính gợi ý) có bản chất khác nhau — tách để `error_type` phản ánh đúng loại lỗi khi dùng làm nguồn cho Rearrange the Block (chỉ `GRAMMAR` mới phù hợp làm bài tập sắp xếp khối, `WRITING_COHERENCE` thì không).

**Ghi chú bổ sung — `VOCABULARY` trong Dictation (Listening)**: ngoài trường hợp đoán nghĩa/dùng từ sai ngữ cảnh, `VOCABULARY` còn dùng cho trường hợp người học **nghe đúng âm nhưng gõ sai chính tả** một từ chuyên ngành/tên riêng chưa từng gặp trong bài Dictation — phân biệt với `LISTENING_COMPREHENSION` (nghe nhầm âm thật sự) bằng khoảng cách ngữ âm (Metaphone). Xem chi tiết cơ chế phân loại ở `feature-listening.md` mục 3.5.

**Ràng buộc migration đề xuất**: dùng Postgres `ENUM` type (không phải `VARCHAR` + CHECK) để đảm bảo toàn vẹn dữ liệu ở tầng DB, khớp cách gọi "enum `error_type` cố định" xuyên suốt 3 file nguồn.

**Cập nhật (rà soát lần 3, `docs/schema.sql`)**: `WRITING_COHERENCE` trước đây là giá trị "mồ côi" (không có flow nào thực sự ghi nó vào `user_errors`). Nay đã có flow cụ thể: cột mới `writing_submissions.rubric_scores` (JSONB, 4 tiêu chí) + trigger `trg_writing_submissions_flag_coherence` — khi bài `extended_topic`/`free_topic` chấm xong và điểm `coherence_cohesion` < 60/100 (ngưỡng đề xuất), tự động insert 1 dòng `user_errors(error_type='writing_coherence')`. Bản thân enum 9 giá trị này vẫn ở trạng thái "chưa chốt chính thức" như ghi ở trên — flow ghi dữ liệu đã có không có nghĩa là danh sách giá trị đã được xác nhận. **Cập nhật 2026-09-24**: trigger này chưa từng tồn tại trong DB thật; flow được thực hiện ở tầng service — `writing_service.submit_essay` gọi `adaptive_service.record_error(..., "writing_coherence", {source, submission_id, coherence_cohesion})` khi `coherence_cohesion < 60` (xem `thiet_ke_database.md` mục 12).

---

## 10. Phụ lục B — Lịch sử đối chiếu ERD (đã xử lý)

> Các điểm lệch từng phát hiện giữa ERD và tài liệu thiết kế đã được xác nhận và fix trong `erd.mermaid`. Giữ lại mục này làm nhật ký đối chiếu, không phải danh sách việc cần làm.

1. ~~Bảng `ACCENTS`~~ — đã xoá khỏi ERD, khớp quyết định loại bỏ mô phỏng accent vùng miền.
2. ~~Bảng `ERROR_LOG`~~ — đã xoá khỏi ERD, thay bằng cặp `quiz_attempts` + `user_errors`.
3. ~~`SCENARIOS` thiếu `goal`/`formality_level`~~ — đã bổ sung 2 cột này vào ERD (đánh dấu "đề xuất" vì logic chấm điểm dùng 2 cột này ở `feature-speaking.md` mục 3 vẫn đang chờ xác nhận — bản thân cột schema thì đã xác nhận có, chỉ rubric/prompt logic dùng nó là còn đề xuất).
4. ~~`WRITING_SUBMISSIONS` thiếu `source_type`/`prompt_text`/`certificate_style`~~ — đã bổ sung 3 cột này vào ERD, khớp `feature-writing.md` mục 1 và `thiet_ke_database.md` mục 7.
5. ~~`WRITING_SUBMISSIONS` thiếu `rubric_scores`~~ — đã bổ sung cột này vào ERD + `docs/schema.sql` (rà soát lần 3/mục 3.10), phục vụ flow tự động `WRITING_COHERENCE` ở Phụ lục A. Response `POST /api/writing/submissions/{id}/submit` (mục 5) cũng đã cập nhật để trả field này.
6. ~~Phạm vi route token Extension chưa quy định (`AUTH-007` `test-cases (1).md`)~~ — đã chốt allow-list (`/api/extension/*` + `/api/reading/lookup` + `/api/vocab`), ghi ở mục 0.2 và mục 8. Middleware enforce còn là TODO code, không phải điểm mở về quyết định nữa.

**Điểm còn mở duy nhất liên quan phần này**: bản thân **logic/rubric** chấm `intent_score`/`politeness_score` (dùng `scenarios.goal`/`formality_level` làm ground-truth) vẫn ở trạng thái đề xuất, chưa xác nhận chính thức — xem `feature-speaking.md` mục 3. Đây là vấn đề về **logic nghiệp vụ**, khác với vấn đề **schema** đã nêu ở các điểm trên (đã xử lý xong).

---

## 11. Ghi chú chung
- Tất cả response object trả trực tiếp field từ model tương ứng (Pydantic `orm_mode`/`from_attributes=True`), không có tầng transform phức tạp trừ khi ghi rõ trong bảng trên.
- Router → `feature_service` → `infra_service`/model, không bỏ qua lớp nào (mục 9.1 đề cương).
