# Tích hợp Frontend ↔ Backend và cấu hình dịch vụ AI (tư liệu cho báo cáo khóa luận)

> Cập nhật: 2026-09-30. Phạm vi: môi trường phát triển (chạy trên máy cá nhân). Việc triển khai online (Render/Vercel) nằm ngoài phạm vi báo cáo này.

## 1. Bối cảnh

Backend FastAPI cung cấp đầy đủ endpoint cho 4 kỹ năng (Reading, Writing, Listening, Speaking) cùng phân hệ Adaptive. Khi rà soát bằng cách đối chiếu danh sách route ở `backend/app/routers/` với các lời gọi trong `frontend-reference/src/api.ts`, có 6 endpoint đã hoàn thiện ở backend nhưng giao diện chưa gọi tới. Mục này ghi lại cách các endpoint đó được nối vào giao diện.

## 2. Các chức năng được nối bổ sung

| Chức năng | Endpoint backend | Vị trí giao diện | Hàm gọi API (`api.ts`) |
|---|---|---|---|
| Đoán nghĩa theo ngữ cảnh (Guess the Context) | `POST /api/reading/guess-context`, `POST /api/reading/guess-context/{id}/submit` | Reading — `ReadingExtrasPanel` | `createGuessContext`, `submitGuessContext` |
| Truyện AI từ từ vựng đã lưu (AI Custom Story) | `POST /api/stories` | Reading — `ReadingExtrasPanel` | `createStory` |
| Gợi ý đề bài | `POST /api/writing/prompts/suggest` | Writing — nút "Suggest a topic" | `suggestWritingPrompt` |
| Viết lại câu yếu nhất (Rephrase) | `POST /api/writing/rephrase` | Writing — sau khi chấm bài | `rephraseSentence` |
| Hàng đợi ôn tập ưu tiên | `GET /api/adaptive/review-queue` | Analytics — khối "Review next" | `getReviewQueue` |

Endpoint `POST /api/writing/grammar-check` (kiểm tra ngữ pháp bản xem trước, không lưu) chưa được nối vì luồng chấm bài đã trả về các lỗi ngữ pháp dưới dạng `insights`; đây là điểm có thể mở rộng sau.

### 2.1 Luồng nghiệp vụ

- **Đoán nghĩa theo ngữ cảnh:** người học nhập một từ → backend sinh câu điền khuyết kèm 4 lựa chọn (không trả đáp án đúng) → người học chọn → backend trả `correct` và `correct_option_index`. Đáp án chỉ lộ sau bước nộp, tránh gian lận phía client.
- **Truyện AI:** giao diện lấy danh sách từ đến hạn ôn (`GET /api/vocab/due`), người học chọn tối đa 15 từ → backend sinh truyện; các từ AI không dùng được trả về ở `missing_terms` để hiển thị cho người học.
- **Gợi ý đề bài:** nếu ô tiêu đề đã có chữ thì coi đó là chủ đề (`topic`); nếu trống thì xin đề theo phong cách chứng chỉ (`certificate_style = ielts`). Backend yêu cầu đúng một trong hai tham số, nếu không sẽ báo lỗi validate. Có thể trả một đề chốt sẵn hoặc danh sách lựa chọn.
- **Rephrase:** dùng `submission_id` của bài vừa chấm; không truyền câu cụ thể thì mô hình tự chọn câu yếu nhất.
- **Review queue:** danh sách hỗn hợp từ vựng và lỗi sai, xếp theo `priority_score`; giao diện hiển thị 6 mục đầu.

### 2.2 Xử lý trạng thái chờ và lỗi

Các thao tác trên đều gọi mô hình ngôn ngữ nên có độ trễ. Giao diện tái sử dụng `ErrorNotice` (thông báo lỗi kèm nút thử lại) và biểu tượng xoay khi đang chờ, thống nhất với `RearrangePanel` sẵn có.

## 3. Kiến trúc chọn nhà cung cấp AI

Cấu hình nằm ở `backend/app/core/config.py` và `backend/.env`:

| Thành phần | Biến môi trường | Giá trị dev | Ghi chú |
|---|---|---|---|
| LLM cho Writing/Reading (sinh đề, chấm, sửa bài) | `LLM_PROVIDER` | `ollama` | Chạy cục bộ; có thể đổi `gemini` |
| Chat Notebook (RAG) | tham số `provider` mỗi request | mặc định `gemini` | Không phụ thuộc `LLM_PROVIDER` |
| Embedding cho RAG | `EMBEDDING_PROVIDER` | `ollama` (bge-m3, 1024 chiều) | `gemini` cho 768 chiều |
| Nhận dạng giọng, chấm phát âm | `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | đã cấu hình | Azure Speech |
| TTS podcast từ tài liệu .docx | `ELEVENLABS_API_KEY` | đã cấu hình | ElevenLabs |

Lý do thiết kế: Ollama chạy cục bộ không tốn hạn mức và giữ dữ liệu trên máy (xem `thuc_nghiem_rag_ollama.md` cho thực nghiệm so sánh), còn Gemini là lựa chọn dự phòng khi không có máy đủ mạnh. Việc đặt provider thành biến môi trường cho phép đổi mà không sửa mã.

### 3.1 Hạn chế cần nêu trong báo cáo

- Chấm bài Writing bằng Ollama cục bộ mất khoảng 25 giây (đo trên máy phát triển); lần gọi đầu sau khi nghỉ còn lâu hơn do phải nạp mô hình.
- Bài Rearrange the Block ở dạng câu có nhiều thứ tự hợp lệ dùng Ollama để xét thứ tự lạ; nếu Ollama không chạy, bài này báo lỗi thay vì chấm theo luật.
- Thông báo lỗi trong `ErrorNotice` đang hướng dẫn khởi động Ollama, phù hợp môi trường phát triển.

## 4. Kiểm thử

- Kiểm tra kiểu TypeScript (`tsc --noEmit`) không lỗi.
- Bộ test frontend (`vitest run`): 29/29 test đạt.
- Các chức năng mới **chưa** có test tự động riêng và **chưa** được kiểm thử thủ công trên trình duyệt với backend thật tại thời điểm ghi tài liệu này; cần bổ sung trước khi đưa số liệu vào báo cáo.

## 5. Việc còn lại

- Kiểm thử thủ công 5 chức năng mới và ghi kết quả vào `kiem_thu_nguoi_dung.md`.
- Cân nhắc nối `grammar-check` nếu muốn có kiểm tra ngữ pháp nhanh khi đang gõ.
- Thêm test cho các hàm API mới trong `api.test.ts`.
