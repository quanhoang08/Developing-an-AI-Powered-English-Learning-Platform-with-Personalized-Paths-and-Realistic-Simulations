# Lumina English Platform — Review kiến trúc & ý tưởng thiết kế

## 1. Review cây thư mục thực tế bạn vừa gửi

### 1.1. Lỗi logic / xung đột cần sửa

| # | Vị trí | Vấn đề | Cách sửa |
|---|---|---|---|
| 1 | `services/` | `speech_service.py` tồn tại **song song** với `stt_service.py`, `tts_service.py`, `pronunciation_service.py` | Trùng lặp — đi ngược quyết định đã chốt (gộp 1 file). Chọn **1 trong 2** hướng (xem mục 2.1 bên dưới), xoá 3 file còn lại (hoặc xoá `speech_service.py` nếu chọn hướng tách). |
| 2 | `services/` | Thiếu `auth_service.py` dù có `routers/auth.py` và `models/user.py` | Thêm `auth_service.py` — chứa logic hash password, tạo/verify JWT, gọi qua `core/security.py` cho phần thuật toán thuần, còn `auth_service.py` điều phối nghiệp vụ (kiểm tra user tồn tại, tạo user mới...) |
| 3 | `backend/migrations/visions` | Sai tên thư mục — Alembic **bắt buộc** đúng tên `versions` | Đổi thành `migrations/versions/` |
| 4 | `backend/alembic.init.schema.sql` | Tên file sai, gộp nhầm khái niệm | File cấu hình Alembic đúng chuẩn tên là `alembic.ini` (định dạng INI, ví dụ `sqlalchemy.url = ...`), không liên quan `schema.sql` gốc |

### 1.2. Lỗi chính tả (ảnh hưởng import path, nên sửa sớm)

| Sai | Đúng | Ảnh hưởng |
|---|---|---|
| `writting.py`, `writting_service.py` (routers, schemas, models, services) | `writing.py`, `writing_service.py` | Sai lan ra mọi `from app.services.writting_service import ...` — càng để lâu càng khó refactor |
| `notebook_serivce.py` | `notebook_service.py` | Tương tự |

### 1.3. Thiếu sót nhỏ

- Thiếu `.env.example` bên cạnh `.env` — cần giữ cả 2, `.env.example` để hội đồng/người khác biết cần khai báo biến gì mà không lộ key thật.
- Chưa thấy `__init__.py` trong `core/`, `models/`, `services/`, `routers/`, `schemas/` — nên thêm (rỗng hoặc export ngắn gọn) để rõ ràng là Python package.
- Chưa có nơi đặt hàm convert audio (webm/mp3 → PCM WAV 16kHz mono) — bắt buộc phải có trước khi audio vào Azure Speech SDK. Đề xuất: `services/audio_utils.py` hoặc gộp thẳng vào `speech_service.py` nếu chọn hướng gộp.

### 1.4. Những phần đã đúng, giữ nguyên

- `models/` tách theo domain (`vocab.py`, `reading.py`, `writing.py`...) + `base.py` chung — đúng chuẩn SQLAlchemy declarative.
- `core/dependencies.py` đã có — đúng vị trí cho `get_db()`, `get_current_user()`.
- `rag_service.py` tách riêng khỏi `llm_service.py` — đúng, vì RAG là logic điều phối (chunk + embed + query), còn `llm_service.py` chỉ là cổng gọi Gemini thuần.
- `docs/architecture_decisions.md` chuyển vào `docs/` — hợp lý, đúng vị trí tài liệu khoá luận.
- `frontend-reference/` giữ nguyên, tách biệt hoàn toàn với `frontend/` thật — đúng như dự định ban đầu (chỉ soi giao diện, không đụng vào).

---

## 2. Tóm tắt ý tưởng thiết kế đã thống nhất

### 2.1. Vấn đề còn treo: gộp hay tách Speech service?

Cây thư mục hiện tại lẫn cả 2 phương án — cần chọn dứt điểm 1 trong 2:

**Phương án A — Gộp 1 file (đã đề xuất trước đó)**
```
services/speech_service.py
    class SpeechService:
        def __init__(self): ...       # khởi tạo SpeechConfig 1 lần
        def speech_to_text(...): ...
        def text_to_speech(...): ...
        def assess_pronunciation(...): ...
```
Ưu điểm: đơn giản, 1 nơi duy nhất chứa toàn bộ logic Azure Speech, dễ tìm.
Nhược điểm: file sẽ dài khi thêm nhiều logic xử lý (convert audio, xử lý lỗi riêng cho từng loại).

**Phương án B — Tách theo capability, ghép qua 1 facade dùng chung client**
```
services/azure_speech_client.py   # chỉ chứa hàm khởi tạo SpeechConfig dùng chung
services/stt_service.py           # nhận SpeechConfig từ azure_speech_client, chỉ lo STT
services/tts_service.py           # tương tự, chỉ lo TTS
services/pronunciation_service.py # tương tự, chỉ lo chấm phát âm
services/speech_service.py        # facade — feature_service (speaking_service...) chỉ import file này,
                                   # bên trong speech_service gọi lại 3 file trên
```
Ưu điểm: mỗi file 1 trách nhiệm (Single Responsibility), dễ viết unit test riêng cho từng capability mà không cần mock cả 3 chức năng cùng lúc, dễ mở rộng nếu sau này đổi provider TTS/STT khác nhau (vd TTS dùng Azure nhưng STT dùng Google) mà không đụng vào 2 file kia.
Nhược điểm: nhiều file hơn, phải quản lý việc truyền `SpeechConfig` xuống 3 module con.

→ **Khuyến nghị cho quy mô khoá luận**: Phương án A (gộp 1 file) — vì khối lượng logic Speech không quá lớn (3 method), gộp giúp trình bày trong báo cáo/bảo vệ đơn giản hơn, và đúng với cách Microsoft trình bày trong docs chính thức của Azure Speech SDK. Phương án B chỉ đáng làm nếu dự đoán sẽ đổi provider STT/TTS riêng lẻ trong tương lai — nếu khoá luận không có yêu cầu đó thì không cần thiết.

### 2.2. `core/config.py` (đã viết)

- Dùng `pydantic-settings`, đọc `.env` 1 lần duy nhất qua `@lru_cache`, expose instance `settings` dùng chung.
- Gom đủ nhóm biến: App, Database (2 URL — 1 async cho app, 1 sync cho Alembic), Auth/JWT, Gemini (model chat tách khỏi model embedding), Azure Speech (key, region, voice/locale mặc định), Storage, CORS.
- Lý do tách `DATABASE_URL` (asyncpg) và `DATABASE_URL_SYNC` (psycopg2): Alembic mặc định chạy đồng bộ, không hỗ trợ tốt driver async — đây là điểm hay bị bỏ sót gây lỗi migration khó hiểu.

### 2.3. `services/llm_service.py` (đã viết)

- Wrap Gemini qua `langchain-google-genai` (`ChatGoogleGenerativeAI`) — không gọi thẳng SDK `google-generativeai` — để dễ đổi provider (Claude/OpenAI) chỉ bằng cách sửa 1 file này.
- 4 method public:
  - `generate_text()` — sinh văn bản tự do (đoạn văn đọc hiểu, gợi ý viết lại câu...)
  - `generate_structured()` — ép Gemini trả đúng Pydantic schema (dùng `with_structured_output()`), cho các trường hợp cần dữ liệu có cấu trúc: câu hỏi trắc nghiệm reading, feedback writing có điểm số theo tiêu chí...
  - `chat()` — hội thoại nhiều lượt cho `speaking_service`, nhận `history` dạng list dict từ DB truyền vào, không tự giữ state
  - `embed_text()` / `embed_documents()` — tách riêng cho `rag_service`, khởi tạo model embedding kiểu lazy (chỉ khởi tạo khi lần đầu được gọi)
- Có retry (exponential backoff, tối đa 3 lần) cho lỗi mạng/timeout tạm thời; KHÔNG retry lỗi bị chặn nội dung hay lỗi cấu hình (retry lúc đó vô ích, chỉ tốn quota).
- Singleton `llm_service` — mọi feature_service khác `import llm_service`, không tự khởi tạo `LLMService()` riêng (đây chính là điểm sửa cho `vocab_service.py` — bước tiếp theo trong kế hoạch).

### 2.4. RAG — phân biệt 2 luồng khác nhau, không dùng chung 1 hàm

- **Reading Classic Mode** (có nguồn thật): RAG truyền thống — tài liệu người dùng upload qua `notebook.py` được `rag_service.py` chunk + embed (qua `llm_service.embed_documents()`) → lưu pgvector → khi hỏi, retrieve top-k chunk liên quan → Gemini trả lời kèm trích dẫn trỏ về đúng `chunk_id`/vị trí trong tài liệu gốc.
- **Reading Skim & Scan / Writing** (sinh nội dung mới): không qua `rag_service`. Gọi thẳng `llm_service.generate_text()` hoặc `generate_structured()` để sinh đoạn văn mới → sau đó tự chunk lại đoạn vừa sinh (không cần lưu pgvector, không cần embedding) để tạo "trích dẫn nội bộ" — tức câu trả lời trỏ về đúng câu trong chính đoạn văn vừa sinh ra, không có nguồn ngoài.

---

## 3. Việc cần làm trước khi viết tiếp `speech_service.py`

1. Sửa 4 lỗi ở mục 1.1 và 2 lỗi chính tả ở mục 1.2 trong cây thư mục thật (đổi tên file/thư mục).
2. Xác nhận chọn **Phương án A hay B** ở mục 2.1 (khuyến nghị: A).
3. Thêm `auth_service.py` vào kế hoạch (dù chưa cần viết ngay, cần biết vị trí để tránh lại thiếu sau này).