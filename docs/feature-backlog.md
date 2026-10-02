# Backlog tính năng mở rộng (ghi nhận 2026-09-30)

> Nguồn: danh sách gợi ý thị trường 2026 (từ vựng, ngữ pháp, IELTS, TOEIC, học sinh, luyện nói, động lực), đã **loại** những mục web đã có (Rephrase/nâng cấp câu, chấm Writing 4 tiêu chí, SM-2, hội thoại tình huống, Azure phát âm, slang/phrasebook, streak/XP, sổ lỗi + quiz adaptive, Dictation, transcript, Rearrange, extension tra từ, weekly summary, Notebook RAG) và mục đã chốt bỏ (nghe nhiều giọng/accent).

## Quy tắc thực hiện (người dùng chốt 2026-09-30)

- Xây theo thứ tự ưu tiên bên dưới, **xây được tới đâu thì tới đó, hết càng tốt**.
- Gặp khó khăn kỹ thuật hoặc **phát sinh chi phí** (key trả phí, gói API, hạ tầng mới) → được phép **bỏ qua** mục đó, ghi lý do vào cột Trạng thái, không dừng cả backlog.
- Mọi migration DB vẫn phải xin phép trước khi áp (xem `lumina_context.md` mục 5); ưu tiên mở rộng bảng có sẵn.
- Mọi mục đều thuộc tier **Thử nghiệm giới hạn / Định hướng mở rộng**, không phải MVP đồ án.

Trạng thái: `[ ]` chưa làm · `[~]` đang làm · `[x]` xong · `[skip]` bỏ (kèm lý do)

## Ưu tiên 1 — tái dùng hạ tầng có sẵn, chi phí thấp

| # | Tính năng | Ghi chú | Trạng thái |
|---|---|---|---|
| 1.1 | Bộ nhớ hội thoại Speaking: AI nhớ lỗi/mục tiêu buổi trước, chủ động cho dùng lại | dùng `user_errors` đưa vào prompt | [x] backend (chưa test thật, chưa có UI) |
| 1.2 | Khôi phục chuỗi bằng quiz 10-15 câu đạt >=70% trong ngày phát hiện đứt (chuỗi >=2) | cột `streaks.lost_streak/lost_on`, migration 0020 | [x] migration 0020 đã có trong DB (head 0022, kiểm tra 2026-10-01); chưa thử tay trên web |
| 1.3 | Bắt lỗi dịch từng chữ từ tiếng Việt (`literal_translation`; tên cũ "Vietnglish" đã đổi thành `literal_translation` ngày 2026-10-01) | prompt Gemini, ghi `user_errors` (nguồn `speaking_literal_translation`), lưu cột `conversation_turns.literal_translation` | [x] backend + UI, đã thử trên web |
| 1.4 | "Nói lại cho tự nhiên" sau mỗi câu Speaking | thêm 1 trường vào phản hồi lượt nói | [x] backend; chỉ có ở phản hồi lượt vừa nói, không lưu DB |
| 1.5 | Mục tiêu 5 phút/ngày (dựa `study_time_log`) | nhắc nhở push/email: [skip] nếu cần dịch vụ trả phí | [skip] trùng với đồng hồ đếm ngược (CountdownTimer, khóa đổi tab) và chế độ bấm giờ đã có; nhắc push/email cũng cần dịch vụ trả phí |
| 1.6 | Từ vựng tự sinh từ lỗi và hội thoại → vào lịch SM-2 | nối `user_errors`/turn → `vocab` | [x] backend `POST /api/vocab/from-errors` (từ vocabulary/spelling nghe sai ở Dictation → thẻ SM-2, tra nghĩa bằng Ollama; không cần migration). Chưa có UI; lỗi Writing/Speaking là cụm/câu nên chưa nối |

## Ưu tiên 2 — luyện thi (IELTS/TOEIC)

| # | Tính năng | Trạng thái |
|---|---|---|
| 2.1 | True/False/Not Given (dạy tìm từ khóa, phân biệt False vs Not Given) | [x] backend: `POST /api/reading/skim-scan/sessions` nhận `question_type: "tfng"` (mặc định `multiple_choice`); 3 lựa chọn cố định True/False/Not Given, đáp án + giải thích (trích từ khóa căn cứ) do LLM sinh, giải thích chỉ trả ở `/submit` (`results[].explanation`). Migration 0022 (cột `reading_answers.explanation`, đã áp 2026-10-01, đã sao lưu). Test `test_reading_tfng_integration.py` (LLM giả, 2/2 pass). **UI xong + đã thử trên web thật (2026-10-01)**: modal Skim & Scan có chọn loại câu hỏi, sau khi nộp hiện đáp án đúng/sai + giải thích (`ReadingView.tsx`, `api.ts`). Câu hỏi TFNG dùng model judge `llama3.1:8b` (temp 0.1) vì qwen2.5:7b mặc định gắn nhãn sai ("Governments are not involved" → Not Given); với judge thử 3 đoạn/13 câu chỉ sai 1 câu ("only observations" → Not Given thay vì False). Còn lẫn lộn False/Not Given ở câu phủ định, 7-8B chưa hoàn hảo |
| 2.2 | Listening: tô đoạn chứa đáp án + phân tích bẫy (dựa transcript có sẵn) | [x] backend `POST /api/listening/podcasts/{id}/comprehension` (4 lựa chọn, `correct_index`, `trap_note`, đoạn căn cứ + `evidence_start_ms/end_ms` định vị bằng `locate_quote` trên transcript; lưu vào bảng `listening_quiz_attempts` (migration 0024, đã áp 2026-10-02, sao lưu `backups/lumina_pre_0024.dump`); chấm ở server qua `POST /api/listening/quizzes/{id}/submit` (idempotent), câu sai ghi `user_errors` loại `listening_comprehension`, cộng XP + tiến độ kỹ năng Listening, lịch sử `GET /api/listening/quizzes`; model judge). Test `test_listening_comprehension.py` (định vị đoạn, 1/1 pass); UI xong trong `PodcastPanel.tsx` (mục Comprehension quiz: chọn đáp án -> hiện đúng/sai, bẫy, tô xanh đoạn căn cứ trong transcript, nút phát đúng đoạn; tsc sạch, chưa thử tay trên trình duyệt). Test với Postgres thật + LLM giả (sinh, nộp, ghi lỗi, idempotent, lịch sử): pass |
| 2.3 | Giả lập IELTS Speaking 3 phần (đồng hồ, cue card, câu hỏi phụ Part 3) + ước lượng band | [x] `POST /api/speaking/ielts/exam` (đề 3 phần), `/ielts/answer` (STT + phát âm Azure + từ/phút), `/ielts/estimate` (band Fluency/Lexical/Grammar từ model judge, Pronunciation quy đổi tuyến tính từ điểm Azure, overall làm tròn 0.5). Lưu mỗi bài vào bảng `ielts_attempts` (migration 0023, đã áp 2026-10-01, đã sao lưu `backups/lumina_pre_0023.dump`; `GET /api/speaking/ielts/attempts` + so sánh với bài trước + mục "Your past tests"). Đề bám đúng chủ đề người học nhập, luôn 4/4/3 câu. UI `IeltsPanel.tsx` ở cuối trang Speaking (đồng hồ chuẩn bị 60s + nói tối đa 120s cho Part 2). Đã gọi thật Ollama: exam/estimate chạy; llama3.1:8b đôi khi sinh cue card 5 ý thay vì 4 và Part 1 lệch chủ đề; band chỉ là ước lượng. Ghi âm trên trình duyệt chưa thử tay. Test `test_ielts_speaking.py` (làm tròn band + lưu/so sánh lịch sử với Postgres thật) pass |
| 2.4 | Báo cáo Speaking: tốc độ nói, số lần ngập ngừng, đa dạng từ | [ ] |
| 2.5 | Kế hoạch học theo band mục tiêu + ngày thi, đếm ngược | [ ] |
| 2.6 | Đếm số loại cấu trúc câu sau khi chấm Writing (Grammatical Range) | [ ] |
| 2.7 | TOEIC: luyện Part 1–7, đề thi thử tính giờ, bẫy Part 2, phân tích lỗi theo Part, dự đoán điểm /990, đọc email/biểu mẫu | [ ] (cần nội dung đề: [skip] nếu không có nguồn hợp lệ) |

## Ưu tiên 3 — từ vựng và ngữ pháp

| # | Tính năng | Trạng thái |
|---|---|---|
| 3.1 | Word family + collocation cho từng từ | [ ] |
| 3.2 | Đặt câu với từ vừa học, AI chấm nghĩa/ngữ pháp/ngữ cảnh | [x] `POST /api/vocab/{id}/check-sentence` + mục "Use it in a sentence" ở panel luyện từ Reading; câu sai ngữ pháp ghi `user_errors` (nguồn `vocab_sentence`); không migration. Chấm bằng Ollama model riêng `OLLAMA_JUDGE_MODEL_NAME` (mặc định `llama3.1:8b`, temp 0.1, có ví dụ mẫu; chưa pull thì lùi về model mặc định). Benchmark 12 câu: qwen2.5:7b temp 0.7 ~72% → llama3.1:8b temp 0.1 ~85%, nhận ra câu vô nghĩa và không còn lẫn chữ Hán; vẫn có thể sai ở câu khó (Gemini chuẩn hơn nếu cần) |
| 3.3 | Cặp từ dễ nhầm (affect/effect...) dạng chọn từ trong câu | [ ] |
| 3.4 | Ngân hàng paraphrase | [ ] |
| 3.5 | Từ vựng theo chủ đề thi + đo độ phủ Academic Word List / TOEIC | [ ] (cần danh sách từ nguồn mở) |
| 3.6 | Các chế độ ôn: nghe điền từ, đánh vần, ghép nghĩa, kéo thả | [ ] |
| 3.7 | Mẹo nhớ tiếng Việt do người học tạo + bình chọn | [ ] |
| 3.8 | Bản đồ ngữ pháp (test đầu vào), bài 3 phút/ngày, bài sửa lỗi, luyện vị trí từ loại | [ ] |
| 3.9 | Giải thích từng đáp án sai + đối chiếu tiếng Việt | [ ] |
| 3.10 | Dán bài báo/link YouTube → chỉnh trình độ, phụ đề song ngữ | [ ] (YouTube vi phạm giới hạn "chỉ audio + .docx": cần chốt lại; [skip] phần video) |
| 3.11 | Nhập từ theo unit sách giáo khoa | [ ] |

## Ưu tiên 4 — phát âm nâng cao và cộng đồng (dễ phát sinh chi phí)

| # | Tính năng | Trạng thái |
|---|---|---|
| 4.1 | Phát âm theo lỗi người Việt (âm cuối, cụm phụ âm, /θ/ /ð/, trọng âm) | [ ] (dùng Azure hiện có) |
| 4.2 | Trò chơi cặp âm dễ nhầm (ship/sheep) | [ ] |
| 4.3 | Shadowing + so sóng âm | [ ] |
| 4.4 | Nhật ký giọng nói 60 giây | [ ] |
| 4.5 | Chế độ "nói thầm" (gõ chữ giữ streak) | [ ] |
| 4.6 | Bảng xếp hạng bạn bè, thử thách nhóm, đấu từ vựng 1-1 | [ ] |
| 4.7 | Ghép cặp luyện nói với người học khác | [ ] (cần realtime: [skip] nếu tốn hạ tầng) |

## Ưu tiên 5 — dành cho học sinh (Định hướng mở rộng)

Chế độ lớp học và giao bài · báo cáo tuần cho phụ huynh · xin phụ huynh đồng ý cho dưới 18 tuổi + lọc nội dung chat · đổi độ khó theo ngày thi. Tất cả `[ ]`.
