"""
Gom toàn bộ biến môi trường về 1 nơi. Không dùng os.getenv() rải rác trong code nữa —
nếu thiếu biến bắt buộc, app sẽ báo lỗi ngay lúc khởi động thay vì lỗi âm thầm lúc runtime.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    gemini_api_key: str
    azure_speech_key: str = ""
    azure_speech_region: str = "southeastasia"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 ngày
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()