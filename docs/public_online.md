# Mở web cho nhiều người dùng (Ollama + Azure Speech giữ nguyên trên máy bạn)

```
Người dùng ─HTTPS─► Cloudflare Tunnel ─► Caddy (web: frontend + /api) ─► FastAPI (api) ─► Postgres (db)
                                                                            ├─► Ollama trên máy host (host.docker.internal:11434)
                                                                            └─► Azure Speech / Gemini / ElevenLabs (cloud)
```
Người dùng chỉ thấy 1 địa chỉ; không cần CORS (frontend và API cùng origin).

## Chạy
1. `backend/.env`: đặt `JWT_SECRET_KEY` thật (chuỗi dài ngẫu nhiên), giữ các key Azure/Gemini. Không cần đặt `CORS_ORIGINS`.
2. `docker compose -f docker-compose.yml -f docker-compose.public.yml up -d --build`
3. Lấy URL: `docker compose -f docker-compose.yml -f docker-compose.public.yml logs cloudflared` (tìm `https://….trycloudflare.com`).
4. Ollama phải chạy trên máy host. Đã đặt biến môi trường người dùng Windows `OLLAMA_NUM_PARALLEL=4` (4 request song song) và `OLLAMA_KEEP_ALIVE=30m` (giữ model trong RAM); Ollama tự nhận từ lần đăng nhập sau. Đổi giá trị thì đặt lại biến rồi thoát hẳn Ollama (khay hệ thống) và mở lại. Kiểm tra: `Select-String $env:LOCALAPPDATA\Ollama\server.log -Pattern NUM_PARALLEL`.

Dừng công khai: `docker compose -f docker-compose.yml -f docker-compose.public.yml down` (dữ liệu DB vẫn còn trong volume).

## Giới hạn cần biết
- URL `trycloudflare` **đổi mỗi lần khởi động lại** và không có cam kết uptime. Muốn URL cố định: cần domain đưa vào Cloudflare, tạo Tunnel trên dashboard (Public hostname → `http://web:80`), rồi đặt `CLOUDFLARED_ARGS=tunnel --no-autoupdate run --token <token>` trong `.env` ở thư mục gốc.
- Chỉ online khi máy bật, Docker và Ollama chạy. Dưới ~10 người cùng lúc thì ổn; GPU/CPU chỉ chạy được số request LLM song song bằng `OLLAMA_NUM_PARALLEL`.
- `ENV=production` bật kiểm tra secret và `AUTH_RATE_LIMIT_PER_MINUTE=20` (rate limit lưu trong RAM 1 process, đủ cho 1 api).
- Email xác minh (`REQUIRE_EMAIL_VERIFICATION=true`) cần `BREVO_API_KEY` + `MAIL_FROM_EMAIL`; không có thì để tắt (mặc định) để người dùng không bị khoá ngoài.
- Extension Chrome mặc định gọi `http://127.0.0.1:8000`; dùng với bản online thì nhập URL công khai vào ô API trong popup và không cần sửa manifest: `*.trycloudflare.com` đã có trong `host_permissions` và `exclude_matches` (domain riêng thì tự thêm; xem `extension/README.md`).
