from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Tập trung toàn bộ cấu hình runtime của backend vào một object duy nhất.
# Pydantic Settings tự đọc biến môi trường và backend/.env, đồng thời kiểm tra kiểu dữ liệu.
class Settings(BaseSettings):
	app_name: str = "Lumina API"
	environment: str = Field(default="development", validation_alias=AliasChoices("ENV", "ENVIRONMENT"))
	debug: bool = False
	secret_key: str = Field(
		default="development-only-change-this-secret-key",
		validation_alias=AliasChoices("SECRET_KEY", "JWT_SECRET_KEY"),
	)
	access_token_expire_minutes: int = 30
	# Email qua Brevo HTTP API (không dùng SMTP vì nhiều host chặn cổng SMTP). BREVO_API_KEY rỗng -> chỉ log mã (dev).
	# MAIL_FROM_EMAIL phải là sender đã xác minh trong Brevo.
	brevo_api_key: str = ""
	# SMTP (vd. Gmail + App Password): SMTP_USER và SMTP_PASSWORD đều có -> dùng SMTP, bỏ qua Brevo.
	smtp_host: str = "smtp.gmail.com"
	smtp_port: int = 587
	smtp_user: str = ""
	smtp_password: str = ""
	mail_from_email: str = "no-reply@lumina.local"
	mail_from_name: str = "Lumina"
	# True (production): chưa xác minh email thì không đăng nhập được.
	require_email_verification: bool = False
	# Số request/phút/IP cho mỗi endpoint /auth/*; 0 = tắt (production đặt ~20).
	auth_rate_limit_per_minute: int = 0
	refresh_token_expire_days: int = 30
	# Độ lệch UTC (giờ) dùng để xác định "ngày học" của streak; mặc định UTC+7 (Việt Nam).
	study_utc_offset_hours: int = Field(
		default=7, validation_alias=AliasChoices("STUDY_UTC_OFFSET_HOURS")
	)
	storage_documents_dir: str = "storage/documents"
	storage_video_dir: str = "storage/videos"
	storage_audio_dir: str = Field(
		default="storage/audio", validation_alias=AliasChoices("STORAGE_AUDIO_DIR")
	)
	cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
	database_url: str = (
		"postgresql+psycopg://lumina_user:changeme_use_a_strong_password"
		"@localhost:5432/lumina_db"
	)
	database_url_sync: str = (
		"postgresql+psycopg://lumina_user:changeme_use_a_strong_password"
		"@localhost:5432/lumina_db"
	)
	google_api_key: str = Field(default="", validation_alias=AliasChoices("GOOGLE_API_KEY"))
	gemini_model_name: str = Field(
		default="gemini-3.6-flash", validation_alias=AliasChoices("GEMINI_MODEL_NAME")
	)
	gemini_temperature: float = Field(
		default=0.7, validation_alias=AliasChoices("GEMINI_TEMPERATURE")
	)
	gemini_max_output_tokens: int = Field(
		default=4096, validation_alias=AliasChoices("GEMINI_MAX_OUTPUT_TOKENS")
	)
	# Model Gemini Live (audio vào/ra theo luồng) cho gọi thoại 2 chiều — xem live_call_service.
	gemini_live_model: str = Field(
		default="models/gemini-2.5-flash-native-audio-latest",
		validation_alias=AliasChoices("GEMINI_LIVE_MODEL"),
	)
	# Gọi thoại chạy hoàn toàn local (chọn "ollama" ở tab Live call): STT faster-whisper + Ollama + TTS Piper,
	# cả hai chạy trên CPU để không tranh VRAM với Ollama. Model tải lần đầu vào local_models_dir (đã mount,
	# không mất khi rebuild container).
	local_models_dir: str = Field(default="storage/models", validation_alias=AliasChoices("LOCAL_MODELS_DIR"))
	whisper_model_name: str = Field(default="small.en", validation_alias=AliasChoices("WHISPER_MODEL_NAME"))
	piper_voice: str = Field(default="en_US-lessac-medium", validation_alias=AliasChoices("PIPER_VOICE"))
	gemini_embedding_model: str = Field(
		default="models/gemini-embedding-001",
		validation_alias=AliasChoices("GEMINI_EMBEDDING_MODEL"),
	)

	# LLM provider mac dinh cho writing/reading (tao de, cham diem, sua bai) --
	# "gemini" hoac "ollama". Chat (Notebook RAG) co provider rieng theo tung request,
	# mac dinh gemini, khong phu thuoc bien nay (xem llm_service.answer_grounded_question).
	llm_provider: str = Field(default="ollama", validation_alias=AliasChoices("LLM_PROVIDER"))
	ollama_base_url: str = Field(
		default="http://localhost:11434", validation_alias=AliasChoices("OLLAMA_BASE_URL")
	)
	ollama_model_name: str = Field(
		default="qwen2.5:7b-instruct-q4_K_M", validation_alias=AliasChoices("OLLAMA_MODEL_NAME")
	)
	# Model riêng cho các tác vụ CHẤM điểm (vd chấm câu đặt với từ vựng): benchmark 9 câu cho thấy
	# llama3.1:8b nhận ra câu vô nghĩa mà qwen2.5:7b bỏ sót. Chưa pull thì tự lùi về ollama_model_name.
	ollama_judge_model_name: str = Field(
		default="llama3.1:8b", validation_alias=AliasChoices("OLLAMA_JUDGE_MODEL_NAME")
	)
	ollama_temperature: float = Field(
		default=0.7, validation_alias=AliasChoices("OLLAMA_TEMPERATURE")
	)
	# Model Ollama tùy biến (Modelfile: SYSTEM + tham số cố định) dành riêng cho RAG chat bám tài liệu —
	# tạo bằng `python modelfiles/create_models.py`. Chưa tạo thì tự lùi về ollama_model_name.
	ollama_rag_model_name: str = Field(
		default="lumina-rag-qwen", validation_alias=AliasChoices("OLLAMA_RAG_MODEL_NAME")
	)

	# Embedding cho RAG: "ollama" (bge-m3 local, đa ngữ, 1024 chiều → cột embedding_local) hoặc
	# "gemini" (cloud, 768 chiều → cột embedding). Chọn theo thực nghiệm experiments/run_retrieval.py.
	embedding_provider: str = Field(default="ollama", validation_alias=AliasChoices("EMBEDDING_PROVIDER"))
	ollama_embedding_model: str = Field(
		default="bge-m3", validation_alias=AliasChoices("OLLAMA_EMBEDDING_MODEL")
	)

	# Chunking cho RAG (xem app/utils/chunking.py): chia theo câu, ~120 từ/chunk, chồng lấp 1 câu.
	chunk_strategy: str = Field(default="sentence", validation_alias=AliasChoices("CHUNK_STRATEGY"))
	chunk_max_words: int = Field(default=120, validation_alias=AliasChoices("CHUNK_MAX_WORDS"))
	chunk_overlap_sentences: int = Field(default=1, validation_alias=AliasChoices("CHUNK_OVERLAP_SENTENCES"))
	# Azure Speech/ElevenLabs: speech_service kiểm tra key rỗng để raise SpeechServiceError rõ ràng thay vì lỗi SDK mơ hồ.
	azure_speech_key: str = Field(default="", validation_alias=AliasChoices("AZURE_SPEECH_KEY"))
	azure_speech_region: str = Field(
		default="southeastasia", validation_alias=AliasChoices("AZURE_SPEECH_REGION")
	)
	azure_speech_default_voice: str = Field(
		default="en-US-AvaMultilingualNeural",
		validation_alias=AliasChoices("AZURE_SPEECH_DEFAULT_VOICE"),
	)
	elevenlabs_api_key: str = Field(
		default="", validation_alias=AliasChoices("ELEVENLABS_API_KEY")
	)

	# Cho phép đọc file .env nhưng bỏ qua các biến dành riêng cho dịch vụ khác.
	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		extra="ignore",
	)


@lru_cache
def get_settings() -> Settings:
	# Cache settings để mọi module dùng cùng một cấu hình trong suốt vòng đời process.
	settings = Settings()
	# Nhiều nhà cung cấp Postgres cấp URL dạng postgres:// hoặc postgresql://; SQLAlchemy cần chỉ rõ driver psycopg.
	for field in ("database_url", "database_url_sync"):
		url = getattr(settings, field)
		for prefix in ("postgres://", "postgresql://"):
			if url.startswith(prefix):
				setattr(settings, field, "postgresql+psycopg://" + url[len(prefix):])
	# Secret mặc định nằm trong mã nguồn công khai -> ai cũng ký được JWT giả. Chặn khởi động ở production.
	if settings.environment == "production" and settings.secret_key.startswith("development-only"):
		raise RuntimeError("SECRET_KEY phải được đặt khi ENV=production")
	return settings
