Lumina English Platform — Kiến trúc Backend (chốt cuối)
1. Nguyên tắc 3 lớp
router (FastAPI endpoint)
   ↓  nhận request, validate bằng Pydantic schema, gọi service, trả response
feature_service (nghiệp vụ theo domain: reading, writing, speaking...)
   ↓  điều phối logic, gọi infra_service khi cần, đọc/ghi DB qua model
infra_service (llm_service, speech_service, rag_service...) + model (SQLAlchemy ORM)
   ↓  giao tiếp trực tiếp với bên ngoài: Gemini API, Azure Speech API, PostgreSQL

Router không bao giờ gọi thẳng llm_service/speech_service — luôn qua feature_service tương ứng. Ví dụ: routers/reading.py → services/reading_service.py → (services/llm_service.py + services/rag_service.py) + models/reading.py.

2. Quyết định kiến trúc
Vấn đề	Quyết định	Lý do
DB access	SQLAlchemy 2.0 async ORM (asyncpg) + Alembic	Alembic autogenerate cần model class; test với DB thật không cần mock nặng; type-safe
Azure Speech	1 file speech_service.py, class SpeechService với 3 method (speech_to_text, text_to_speech, assess_pronunciation), SpeechConfig khởi tạo 1 lần	Đúng khuyến nghị SDK chính thức; tránh duplicate init
LLM (Gemini)	1 file llm_service.py, wrap qua langchain-google-genai (ChatGoogleGenerativeAI)	Dễ đổi provider (Claude/OpenAI) sau này mà không sửa feature_service, đúng comment gốc trong cây thư mục
RAG cho Reading	Có 2 luồng khác nhau, không dùng chung 1 hàm: (a) Classic Mode — RAG thật trên tài liệu người dùng upload (embed vào pgvector, retrieve top-k, cite theo chunk_id); (b) Skim & Scan — Gemini sinh đoạn văn mới, sau đó tự chunk lại đoạn vừa sinh để tạo "self-citation" (trỏ về câu trong chính đoạn văn, không cần nguồn ngoài)	Bản chất 2 use-case khác nhau: (a) grounding trên sự thật có sẵn, (b) sinh nội dung mới
Audio format	Client gửi lên (webm/mp3) → convert PCM WAV 16kHz mono bằng pydub/ffmpeg trước khi đưa vào Azure SDK	Azure Speech SDK & Pronunciation Assessment bắt buộc định dạng này
Mock trong test	Hạn chế tối đa — dùng DB test thật (docker Postgres riêng cho test) và chỉ mock ở boundary thật sự không thể gọi thật (Azure/Gemini tốn phí mỗi lần chạy CI)	Đúng tinh thần khoá luận: hạn chế mock, tăng tính thực tiễn