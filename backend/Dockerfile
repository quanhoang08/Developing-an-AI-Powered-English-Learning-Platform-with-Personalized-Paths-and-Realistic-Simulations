FROM python:3.11-slim

WORKDIR /app

# libpq-dev + gcc: cần để build asyncpg/psycopg2 từ source trên 1 số nền tảng.
# ffmpeg: BẮT BUỘC cho pydub (audio_utils.py) — dùng để convert audio client
# gửi lên (webm/mp3) sang PCM WAV 16kHz mono trước khi đưa vào Azure Speech SDK.
# Thiếu ffmpeg thì pydub sẽ raise lỗi "ffmpeg not found" ngay khi gọi convert,
# đây là lỗi rất hay bị bỏ sót khi deploy vì máy dev cá nhân thường đã cài sẵn ffmpeg.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Đảm bảo thư mục lưu file tồn tại kể cả khi volume chưa mount lần đầu
RUN mkdir -p storage/documents storage/audio

EXPOSE 8000

# Mặc định chạy production (không --reload). docker-compose.yml override
# command này thành có --reload cho môi trường dev.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]