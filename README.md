# Developing-an-AI-Powered-English-Learning-Platform-with-Personalized-Paths-and-Realistic-Simulations

## Chạy demo (Windows + Docker Desktop)

1. Mở **Docker Desktop**, chạy `docker ps` và đợi thấy `lumina_db` (healthy) và `lumina_api`.
   Chưa có thì chạy `docker compose up -d` ở thư mục gốc (thêm `--build` nếu vừa sửa code backend — compose không bật `--reload`).
2. `cd frontend-reference && npm install && npm run dev`. Terminal phải in `Backend OK: http://127.0.0.1:8000`.
   Nếu in `WARNING: backend not reachable` thì quay lại bước 1.
3. Mở trang web bằng **http://localhost:3000** (Swagger của API: http://127.0.0.1:8000/docs).

**Trang mở bằng `localhost:3000`, nhưng API phải gọi bằng `127.0.0.1:8000`.** Trên Windows + Docker Desktop,
`localhost:8000` phân giải ra `::1` (IPv6) trước, nơi `wslrelay.exe` giữ cổng nhưng không chuyển tiếp được vào
container: request treo hoặc reset lúc được lúc không, web báo "Can't reach the Lumina server". Đo thực tế trên
cổng 8000: `127.0.0.1` 30/30 request thành công, `localhost` 0/30. Frontend và extension đã mặc định
`127.0.0.1:8000`; `src/api.test.ts` chặn việc đổi lại.

Đừng mở trang bằng `127.0.0.1:3000`: `CORS_ORIGINS` trong `backend/.env` chỉ cho phép `localhost:3000` và
`localhost:5173`, nên trình duyệt sẽ chặn mọi request tới API. Muốn dùng thì thêm `http://127.0.0.1:3000` vào
`CORS_ORIGINS` rồi `docker compose up -d --no-deps api`.

## Test

`cd frontend-reference && npm test` — chạy hoàn toàn trên máy, không cần Docker hay backend.
