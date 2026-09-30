# Triển khai online: Render (backend + DB) + Vercel (frontend) + Brevo (email) + GitHub Actions (CI)

```
Người dùng ──► Vercel (SPA tĩnh) ──gọi API──► Render web service (FastAPI, Docker) ──► Render Postgres (pgvector)
                                                        └──► Brevo API (gửi mã OTP)   └──► Gemini API
GitHub push ─► Actions CI (test) ─xanh─► Render tự deploy;  Vercel tự deploy khi push
```

## 0. Chuẩn bị
- Đẩy repo lên GitHub (repo phải có `render.yaml`, `.github/workflows/ci.yml`).
- Tài khoản: Render, Vercel, Brevo (đều đăng nhập bằng GitHub/email), Google AI Studio (Gemini key).

## 1. Brevo (gửi OTP)
1. Brevo > Senders, domains & dedicated IPs > **Add a sender**: dùng email của bạn, bấm link xác nhận trong mail Brevo gửi. Không cần tên miền riêng.
2. Brevo > SMTP & API > **API keys** > tạo key. Đây là `BREVO_API_KEY`; `MAIL_FROM_EMAIL` = đúng email sender vừa xác minh.
3. Lưu ý: gửi từ Gmail/Yahoo qua Brevo không có tên miền riêng dễ vào spam; khi test hãy nhắc người tham gia kiểm tra mục Spam. Gói miễn phí có hạn mức mail/ngày (xem trang giá Brevo).

## 2. Render (backend + DB)
1. Render > **New > Blueprint** > chọn repo. Render đọc `render.yaml`, tạo DB `lumina-db` và service `lumina-api`.
2. Điền các biến `sync: false`: `GOOGLE_API_KEY`, `BREVO_API_KEY`, `MAIL_FROM_EMAIL`, `CORS_ORIGINS` (điền sau bước 3 khi biết địa chỉ Vercel).
3. **Nạp schema một lần** (DB mới còn trống; `alembic` chỉ bổ sung phần sau schema gốc). Trên máy bạn, lấy *External Database URL* của `lumina-db` rồi chạy:
   ```bash
   psql "<External Database URL>" -v ON_ERROR_STOP=1 -f schema.sql
   ```
   Sau đó bấm **Manual Deploy** ở `lumina-api`; `preDeployCommand` sẽ chạy `alembic upgrade head`.
4. Kiểm tra `https://<lumina-api>.onrender.com/docs` mở được.

Lưu ý gói: `starter` (trả phí) để không bị ngủ và chạy được preDeployCommand. Gói miễn phí của Render ngủ khi không dùng và ổ đĩa không giữ file, không hợp để kiểm thử người dùng. File upload (Notebook/audio) lưu trong container nên **mất khi redeploy** — cần Render Disk hoặc object storage nếu muốn giữ. Tên/giá gói xem trang giá Render, tôi không chắc số hiện hành.

## 3. Vercel (frontend)
1. Vercel > **Add New Project** > chọn repo > **Root Directory = `frontend-reference`** (đọc `vercel.json`).
2. Environment Variables: `VITE_BACKEND_URL=https://<lumina-api>.onrender.com` (không có dấu `/` cuối). Deploy.
3. Quay lại Render đặt `CORS_ORIGINS=["https://<ten-app>.vercel.app"]` và redeploy (thiếu bước này trình duyệt sẽ chặn mọi request).

## 4. GitHub Actions (CI)
`.github/workflows/ci.yml` chạy mỗi lần push `main` và mỗi PR:
- **backend**: dựng Postgres pgvector, nạp `schema.sql`, `alembic upgrade head`, chạy pytest (các test không cần LLM).
- **frontend**: `npm ci`, `tsc --noEmit`, `vitest`, `vite build`.

Nối CI với deploy (CD): `render.yaml` đã đặt `autoDeployTrigger: checksPass` nên Render chỉ deploy khi CI xanh. Vercel tự deploy bản preview cho mỗi PR và bản production khi merge vào `main`. Nên bật *Branch protection* cho `main` (Settings > Branches) bắt buộc CI xanh trước khi merge.

## 5. Kiểm tra sau khi lên
1. Đăng ký email thật → nhận mã 6 số → nhập → vào được app.
2. "Forgot password?" → nhận mã → đặt mật khẩu mới → đăng nhập.
3. Thử Writing/Reading để chắc Gemini key hoạt động.

## Giới hạn đã biết
- Test cần LLM/Azure/Ollama không chạy trong CI (không có key); chỉ chạy được trên máy có đủ dịch vụ.
- Embedding Notebook: production dùng Gemini (768 chiều), tài liệu tạo ở máy dev bằng bge-m3 cần upload lại.
- Chưa có giới hạn tần suất cho `/auth/*` (mỗi mã OTP chỉ cho nhập sai 5 lần, nhưng xin mã mới vẫn gửi được mail liên tục).
