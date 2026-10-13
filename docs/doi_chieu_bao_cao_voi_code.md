# Đối chiếu báo cáo khóa luận (main.pdf) với code — 2026-10-13

> Nguyên tắc: **code là chuẩn**, không lấy các file `.md` trong `docs/` làm chuẩn. Mỗi số liệu dưới đây được kiểm tra trực tiếp: chạy `app.routes`, `get_settings()`, truy vấn DB, `pytest --collect-only`, chạy `vitest`, đọc `requirements.txt`/`package.json`, đọc hằng số trong service. Không kiểm tra lại được các phép đo thủ công lịch sử (thời gian chờ, kết quả thử trên trình duyệt, Lighthouse...) — những mục đó không nằm trong danh sách "đã khớp" bên dưới.

## A. Các điểm LỆCH cần sửa trong báo cáo

| # | Vị trí trong báo cáo | Báo cáo ghi | Code thực tế | Cách sửa đề xuất |
|---|---|---|---|---|
| 1 | Bảng 5.1 (mục 5.2) | Pydantic **2.9** | `requirements.txt`: `pydantic==2.14.1` (chính mục 4.1.4 của báo cáo nói đã nâng 2.9.2 → 2.14.1 khi thêm Gemini Live) | Sửa thành 2.14; thêm dòng cho `google-genai 2.29`, `faster-whisper 1.2.1`, `piper-tts 1.8.0`, `pypdf 4.3.1`, `python-docx 1.1.2` (bảng hiện thiếu các thư viện của F22 và đọc PDF) |
| 2 | Mục 4.6.1; Bảng A.1 | Access token hết hạn sau **30 phút** | Mặc định trong `config.py` là 30, **nhưng `backend/.env` đang đặt `ACCESS_TOKEN_EXPIRE_MINUTES=1440` (24 giờ)** nên bản đang chạy/demo là 24 giờ | Hoặc ghi rõ "mặc định 30 phút; cấu hình demo đặt 24 giờ", hoặc đặt lại `.env` về 30 trước khi bảo vệ |
| 3 | Mục 4.1.2 + Hình 4.2 + Hình 4.10 (top-5) so với mục 6.3 | Hệ thống truy hồi **5** đoạn; chương 6 không nêu top-k | `rag_service.retrieve_relevant_chunks(top_k=5)`; nhưng `experiments/run_generation.py` dùng `TOP_K = 3` (ghi trong `generation_test.md`) | Thêm 1 câu vào mục 6.3.1: thực nghiệm sinh câu trả lời dùng top-3, hệ thống thật dùng top-5 và chưa được đo riêng; hoặc chạy lại với `TOP_K = 5` |
| 4 | Phần Tóm tắt (trang iv) | "chia cứng theo số từ chỉ đạt 0,875 đến 0,917" | `retrieval.md`: chia cứng **200 từ đạt độ bao phủ 1,0**; chỉ cỡ 60 từ (0,875) và 120 từ (0,917) thấp hơn | Thêm "ở cỡ 60 và 120 từ" (mục 7.1 đã viết đúng, chỉ Tóm tắt thiếu) |
| 5 | Bảng 4.1 (mục 4.1.5) | Liệt kê mô hình chấm Llama cho: kiểm tra câu, TFNG, câu hỏi nghe, đề/band IELTS, sinh+giải đề TOEIC | Mô hình chấm (`_judge_json`) còn được dùng cho: `generate_practice_question` (bộ nhớ hội thoại), `judge_silent_answer` (lọc nói thầm), `generate_word_family`, `adapt_text_level` (viết lại đoạn dán vào). Mô hình mặc định (Qwen) còn làm chấm Writing (`grade_open_essay`, `check_grammar`, `rephrase`), tóm tắt tài liệu, quiz thích ứng, hội thoại, truyện | Thêm các dòng đó vào Bảng 4.1 (hoặc ghi "gồm, nhưng không giới hạn ở") |
| 6 | Mục 5.3 | services khoảng **7.700** dòng; frontend khoảng **11.800** dòng TS | `app/services/*.py` = **8.316** dòng; `frontend-reference/src` (không tính test) = **12.306** dòng | Cập nhật số (hoặc ghi "khoảng 8.300" và "khoảng 12.300") |
| 7 | Mục 4.5 | 136 thao tác HTTP trên 124 đường dẫn "dưới tiền tố /api" + 1 WebSocket | Dưới `/api`: **135** thao tác HTTP trên **123** đường dẫn, + 1 WebSocket `/api/speaking/live`. Con số 136/124 chỉ đúng nếu tính cả `/health` (nằm ngoài `/api`) | Sửa thành 135/123, hoặc ghi "136 thao tác HTTP (gồm `/health`)" |
| 8 | Mục 5.6 | "tệp lược đồ gốc được sinh lại sau mỗi lần chạy di trú" | Khi viết, `schema.sql` gốc dừng ở revision 0034 và **thiếu bảng `live_calls`** (migration 0035). Đã sinh lại 2026-10-13 và kiểm tra áp lên DB rỗng ra 53 bảng | Không cần sửa báo cáo nữa (đã sửa code/tài liệu); chỉ cần nhớ chạy lại bước này sau mỗi migration mới |

## B. Số liệu đã thay đổi SAU khi báo cáo được viết (cập nhật nếu muốn khớp ngày nộp)

| Mục | Báo cáo | Hiện tại |
|---|---|---|
| Thư viện slang (6.3.6, Phụ lục C...) | 48 cụm | **80 cụm** (thêm 32 cụm bằng `seed_slang_extra.py`; casual 40 / neutral 25 / formal 15) |
| Ngân hàng TOEIC (5.4.6, 6.4.2, 7.2, Bảng C.1) | 109 đơn vị (23/13/10/40/5/18) | Part 7 tăng lên 20 (tổng 111) ở 2026-10-13; đợt dựng đang chạy, Gemini hết hạn mức nên tăng rất chậm |
| Số dòng, số thao tác API | xem A.6, A.7 | — |

## C. Các điểm ĐÃ KHỚP với code (đã kiểm tra)

- **Quy mô:** 53 bảng (khớp từng tên bảng ở Bảng 4.2 với DB thật: 0 khác biệt); 35 tệp di trú Alembic; 48 tệp kiểm thử; 291 hàm `def test_`; **306 ca** (`pytest --collect-only`); 18 mô-đun router; Vitest **33/33 đạt** (chạy lại hôm nay: 4 tệp).
- **Cấu hình mặc định (Bảng A.1):** `LLM_PROVIDER=ollama`, `OLLAMA_MODEL_NAME=qwen2.5:7b-instruct-q4_K_M`, `OLLAMA_RAG_MODEL_NAME=lumina-rag-qwen`, `OLLAMA_JUDGE_MODEL_NAME=llama3.1:8b`, `EMBEDDING_PROVIDER=ollama` (bge-m3, 1024 chiều), chia đoạn theo câu 120 từ chồng lấp 1, refresh token 30 ngày, múi giờ UTC+7, vùng Azure mặc định `southeastasia` (`.env` demo dùng `japaneast`), Gemini Live `models/gemini-2.5-flash-native-audio-latest`, Whisper `small.en`, Piper `en_US-lessac-medium`, `REQUIRE_EMAIL_VERIFICATION=false`, rate limit mặc định 0, `ENV=production` chặn khóa JWT mặc định, CORS mặc định 2 nguồn cổng 3000.
- **Bảo mật:** OTP 10 phút, tối đa 5 lần thử, băm có trộn `user_id`; cửa sổ giới hạn tần suất 60 giây; JWT HS256; refresh token xoay vòng.
- **Cơ sở dữ liệu:** `document_chunks` có hai cột vector 768 và 1024; `users` có `email_verified_at/target_band/exam_date/timer_mode_enabled`; `streaks` có `freezes_available/lost_streak/lost_on`; 5 nguồn video, 340 dòng phụ đề, 8 tình huống.
- **Chuỗi ngày/XP:** 1 lượt miễn mỗi 7 ngày, tối đa 2; khôi phục cần ≥10 câu và ≥70%; XP: ôn từ 5, nói thầm 3, lượt nói 10, cuộc gọi 20; nói thầm: ≥8 từ, ≥5 từ khác nhau, 5 lần được cộng XP/ngày.
- **Cuộc gọi thoại hai chiều (4.1.4):** tối đa 600 giây; khung >64 KB bị bỏ; tin nhắn đầu trong 10 giây; VAD: ngưỡng RMS ≥400 hoặc 3× nền ồn, 2 khung để bắt đầu, giữ 2 khung đệm trước, kết thúc sau 0,7 giây im lặng, bỏ đoạn <0,3 giây, cắt >30 giây, chế độ nghiêm ngặt nhân đôi ngưỡng và cần 3 khung; lịch sử 20 tin nhắn; bản chép nối lại cắt 30 dòng × 500 ký tự; không gọi chấm phát âm và không ghi `user_errors` (đúng như báo cáo viết).
- **Quy trình AI:** Azure STT có thử lại rồi dự phòng Gemini; timeout Gemini 30 giây / Ollama 120 giây; giữ mô hình 30 phút (`keep_alive="30m"`); điểm ưu tiên ôn tập đúng công thức (5.1), (5.2); SM-2; chia đoạn: viết tắt `e.g., Dr., TP.`, phần lặp ≤ một nửa cỡ đoạn; ngưỡng phát hiện tiếng Việt 2%; đề thi thử: 6+26+39+30+30+15+54 = 200 câu, 36 giây/câu; kiểm chứng đề TOEIC bằng 2 lượt giải xáo thứ tự.
- **Triển khai:** có `.github/workflows/ci.yml` với 2 job (backend, frontend); `docker-compose.public.yml` (cổng API chỉ lắng nghe 127.0.0.1, container cloudflared); frontend tách mã theo màn hình (6 trang `lazy`).
- **Thực nghiệm (Chương 6):** các Bảng 6.3, 6.5, 6.6, 6.7 khớp từng số với `experiments/results/retrieval.md`, `generation_test.md`, `small_model.md` (Mistral bịa 19/40 = 48%; hiệu ghép cặp và dấu ★ khớp).

## D. Lưu ý khác (không phải sai lệch, nhưng hội đồng có thể hỏi)

1. `requirements.txt` vẫn liệt kê `langchain`, `langchain-google-genai`, `langchain-community` nhưng **không file nào import** (đã grep). Báo cáo không nhắc LangChain nên không sai; chỉ thừa phụ thuộc.
2. Hai thực nghiệm mới (chấm Writing, bộ đếm cấu trúc câu) chưa có trong báo cáo — xem `docs/thuc_nghiem_bo_sung.md`.
