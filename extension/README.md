# Lumina Word Lookup (Chrome/Edge, Manifest V3)

Extension tra nghĩa khi rê chuột trên mọi trang web và lưu từ vào danh sách từ vựng của tài khoản Lumina.

## Hành vi

- **Rê chuột vào từ tiếng Anh** (~0,3 giây) → tooltip hiện IPA, nghĩa tiếng Việt, định nghĩa tiếng Anh, ví dụ. Không cần đăng nhập.
- **Chuột phải** vào từ (hoặc bôi đen tối đa 3 từ) → "Thêm từ vào danh sách từ vựng". Cần đăng nhập ở popup.
- Nút "＋ Lưu vào từ vựng" trong tooltip làm cùng việc.
- Không chạy trên web Lumina (`localhost:3000`, `localhost:5173`). Ở web, tra nghĩa chỉ có trong Reading (passage từ file upload) và Writing (bài đã được AI sửa) — xem `frontend-reference/src/components/WordHoverLookup.tsx`.

## Nguồn dữ liệu

Tooltip hiện 2 tầng, nghĩa tiếng Việt luôn ở trên:

1. **Kết quả nhanh (mọi người dùng, không cần đăng nhập):** nghĩa Việt từ [MyMemory](https://mymemory.translated.net) + định nghĩa/IPA từ [Free Dictionary API](https://dictionaryapi.dev). Từ điển timeout sau 3 giây nên không chặn nghĩa Việt.
2. **Nâng cấp bằng Ollama (chỉ khi đã đăng nhập):** gọi `POST /api/reading/lookup`, backend dùng **Ollama** (không tốn quota Gemini) để chia từng nghĩa kiểu Cambridge: level CEFR (A1–C2) + loại từ + nghĩa tiếng Việt + ví dụ, nghĩa hợp ngữ cảnh câu đứng đầu. Mất ~10–30 giây khi chưa cache; lỗi/Ollama tắt thì giữ kết quả nhanh.
- Lưu từ: `POST /api/vocab` của backend với `source_url` là URL trang đang đọc (backend yêu cầu đúng 1 trong `document_id`/`source_url`).

## Cấu trúc

- `manifest.json`
- `background.js`: service worker — tra từ (có cache), đăng nhập/refresh token, lưu từ, menu chuột phải. Mọi request cross-origin đi qua đây nên không vướng CORS.
- `content-script.js`: bắt hover/chuột phải, dựng tooltip trong Shadow DOM.
- `popup/`: đăng nhập, đăng xuất, bật/tắt tra nghĩa, cấu hình API URL.

## Chạy thử

1. Chạy backend (`http://localhost:8000`) và tạo tài khoản trên web.
2. Vào `chrome://extensions` (hoặc `edge://extensions`), bật Developer mode.
3. Chọn Load unpacked → trỏ tới thư mục `extension`.
4. Mở popup, đăng nhập bằng tài khoản Lumina.
5. Mở một trang tiếng Anh bất kỳ và rê chuột vào một từ.

## Khi deploy web lên domain thật

Thêm domain của web vào `content_scripts[0].exclude_matches` trong `manifest.json`, nếu không tooltip của extension sẽ chạy song song với tooltip của web. Nếu backend không ở `localhost:8000`, thêm origin của nó vào `host_permissions`.
