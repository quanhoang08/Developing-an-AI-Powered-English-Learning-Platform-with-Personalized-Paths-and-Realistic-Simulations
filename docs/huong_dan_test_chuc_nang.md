# Hướng dẫn test từng chức năng & kết quả mong đợi — Lumina

Tài liệu test thủ công (qua giao diện web) kèm lệnh tự động. Test case chi tiết theo spec ở backend xem thêm `test-cases (1).md`; test người dùng cuối xem `kiem_thu_nguoi_dung.md`.

## 0. Chuẩn bị môi trường

| Bước | Lệnh / thao tác | Kết quả mong đợi |
|---|---|---|
| 1 | Mở Docker Desktop | `lumina_db`, `lumina_api` (cổng 8000) tự chạy |
| 2 | `cd frontend-reference && npm run dev` | Web chạy tại http://localhost:3000 |
| 3 | Mở http://localhost:8000/docs | Thấy Swagger UI liệt kê các nhóm: auth, users, vocab, reading, listening, writing, speaking, toeic, grammar, adaptive, activity, gamification, classes, friends, diary, extension, movie-context, pronunciation |
| 4 | Sau khi sửa code backend: `docker restart lumina_api` | API khởi động lại, code mới có hiệu lực (`--reload` trên Windows không đáng tin) |
| 5 | Migration (nếu có): `docker exec lumina_api alembic upgrade head` | Không lỗi, DB lên bản mới nhất |

**Lưu ý chung**
- LLM mặc định là Ollama (local, chậm 30–80 giây/bài); chỉ chọn Gemini ở Speaking/Chat khi cần. Lỗi `ai_quota_exceeded` / 429 khi chạy nhiều test liên tiếp là do quota/rate-limit, không phải bug.
- Cần tài khoản đã đăng nhập cho mọi chức năng bên dưới (trừ mục 1).
- Mỗi chức năng AI thất bại phải hiện **thông báo lỗi dễ hiểu** (ErrorNotice), không trắng trang.

### Chạy test tự động (backend)

```bash
MSYS_NO_PATHCONV=1 docker exec lumina_api python -m pytest tests/<file>.py -q -p no:warnings
```
- Chạy **từng file một** (chạy cả bộ cùng lúc sẽ dính rate-limit đăng ký 429 và quota Gemini).
- Kỳ vọng: `N passed`. Ngoại lệ đã biết: `test_vocab.py::test_health_check` fail do env `production` (không liên quan).
- Test frontend: `cd frontend-reference && npx vitest run` → toàn bộ pass.

---

## 1. Xác thực & tài khoản (Auth / Users)

| # | Cách test | Kết quả mong đợi |
|---|---|---|
| 1.1 | Đăng ký email + mật khẩu hợp lệ | Tạo tài khoản (201); yêu cầu xác minh email |
| 1.2 | Đăng ký trùng email | Báo lỗi email đã tồn tại, không tạo thêm |
| 1.3 | Đăng nhập đúng | Nhận access + refresh token, vào Dashboard |
| 1.4 | Đăng nhập sai mật khẩu | 401, thông báo chung chung (không lộ email có tồn tại hay không) |
| 1.5 | Đăng ký/đăng nhập liên tục nhiều lần | Sau ngưỡng bị chặn 429 (rate limit) |
| 1.6 | Quên mật khẩu → dùng link reset → đăng nhập mật khẩu mới | Mật khẩu cũ không còn dùng được |
| 1.7 | Xác minh email bằng link; "gửi lại mail xác minh" | Tài khoản được đánh dấu đã xác minh |
| 1.8 | Token hết hạn → thao tác bất kỳ | Tự refresh; nếu refresh hỏng → về màn đăng nhập |
| 1.9 | Gọi API không kèm token (ví dụ `GET /api/users/me`) | 401 |
| 1.10 | Sửa hồ sơ (`PATCH /users/me`: tên, mục tiêu, trình độ) | Lưu thành công, tải lại trang vẫn giữ |
| 1.11 | User A truy cập tài nguyên (document, bài viết...) của user B | 404 (không phải 403) |

Test tự động: `test_auth_integration.py`, `test_auth_rate_limit.py`.

---

## 2. Dashboard & Analytics (Adaptive Progress)

| # | Cách test | Kết quả mong đợi |
|---|---|---|
| 2.1 | Mở Dashboard khi tài khoản mới | Hiển thị trạng thái trống hợp lý (0 streak, chưa có hoạt động), không lỗi |
| 2.2 | Làm 1 hoạt động bất kỳ (vd. ôn 1 từ) rồi quay lại Dashboard | Hoạt động gần đây (`/activity/recent`) và tổng kết tuần (`/activity/weekly-summary`) tăng tương ứng |
| 2.3 | Học đủ thời gian để bộ đếm (study timer) chạy | Thời gian học tăng, không đếm khi tab bị ẩn/khóa |
| 2.4 | Mở Adaptive Progress | Thấy lỗi thường gặp (`/activity/errors`), hàng đợi ôn tập, thói quen học (`/activity/habits`: khung giờ, kỹ năng ưu tiên) |
| 2.5 | Tạo quiz thích ứng (`/adaptive/quizzes/generate`) rồi nộp (`/attempts`) | Sinh quiz từ lỗi cũ của user; nộp xong có điểm, lỗi sai được ghi vào nhật ký lỗi |
| 2.6 | Study plan (`GET /users/me/study-plan`) | Trả kế hoạch học phù hợp mục tiêu/trình độ |
| 2.7 | Streak & Gamification (`/gamification/streaks`, `/skills`) | Học mỗi ngày → streak +1; bỏ 1 ngày → về 0, trừ khi có streak freeze |
| 2.8 | Dùng Streak Freeze | Bỏ lỡ 1 ngày vẫn giữ streak, freeze bị trừ |

Test tự động: `test_activity.py`, `test_adaptive.py`, `test_gamification.py`, `test_streak_freeze.py`, `test_study_plan.py`.

---

## 3. Knowledge Space (Notebook)

| # | Cách test | Kết quả mong đợi |
|---|---|---|
| 3.1 | Upload file `.docx` | Tài liệu xuất hiện trong danh sách, trạng thái xử lý rồi "sẵn sàng" |
| 3.2 | Upload file PDF/ảnh/video | Bị từ chối với thông báo (hệ thống chỉ nhận audio và .docx) |
| 3.3 | Bấm hủy khi đang upload | Upload dừng, không để lại tài liệu dở |
| 3.4 | Tạo/đổi tên/xóa thư mục (`notebook-folders`) | Danh sách cập nhật; xóa thư mục không làm mất lỗi giao diện |
| 3.5 | Mở tài liệu, xem nội dung (`/documents/{id}/content`) | Hiển thị các đoạn văn bản đã tách |
| 3.6 | Tạo tóm tắt (overview) | Có tóm tắt đúng nội dung tài liệu, dùng được lại không cần sinh lại |
| 3.7 | Tìm kiếm trong Knowledge Base | Trả đoạn liên quan nhất tới câu truy vấn |
| 3.8 | Chat với tài liệu: hỏi 1 câu có trong tài liệu | Trả lời bám tài liệu (RAG); lịch sử chat lưu lại khi tải lại |
| 3.9 | Hỏi câu ngoài tài liệu | Nói rõ không tìm thấy thông tin, không bịa |
| 3.10 | Sửa tên / xóa tài liệu | Cập nhật / biến mất; chunk liên quan bị xóa theo |
| 3.11 | Animation: bóng rổ (ném bóng khi upload, bóng nhích theo tay khi ngắm) | Hoạt ảnh chạy mượt, không treo UI |

Test tự động: `test_notebook_integration.py`, `test_notebook_chat_integration.py`, `test_chunking.py`, `test_rag_local_pipeline.py`.

---

## 4. Reading & Vocabulary

### 4.1 Reading
| # | Cách test | Kết quả mong đợi |
|---|---|---|
| R1 | Classic mode từ 1 tài liệu → làm hết câu → nộp | Có điểm, đáp án đúng/sai, câu sai được ghi vào nhật ký lỗi |
| R2 | Skim & Scan: sinh bài đọc → trả lời → nộp | Có bài đọc sinh bởi AI, chấm điểm sau khi nộp |
| R3 | True/False/Not Given | Chấm đúng 3 nhãn, hiển thị giải thích |
| R4 | Guess-from-context (`/guess-context`) | Chọn nghĩa từ trong ngữ cảnh; nộp có phản hồi |
| R5 | Rearrange the block (Reading) | Kéo sắp xếp đoạn; điểm tính theo tỷ lệ khối đúng vị trí (chấm một phần) |
| R6 | Rê chuột vào từ (WordHoverLookup) / `POST /reading/lookup` | Hiện nghĩa, phiên âm; có nút lưu vào sổ từ |
| R7 | Adapt Text (`/reading/adapt`) | Văn bản được viết lại theo trình độ chọn (dễ hơn/khó hơn), giữ ý chính |
| R8 | Truyện (`/stories`) | Mở và đọc được, có tra từ |

### 4.2 Vocabulary
| # | Cách test | Kết quả mong đợi |
|---|---|---|
| V1 | Thêm từ mới thủ công (`POST /vocab`) | Từ vào sổ, hiển thị trong danh sách |
| V2 | Tạo từ từ lỗi sai (`from-errors`) | Các từ sai được thêm thành thẻ ôn |
| V3 | Ôn tập lặp lại ngắt quãng: lấy từ đến hạn (`/vocab/due`) → đánh giá (`review`) | Từ trả lời tốt thì hẹn lại xa hơn, trả lời sai thì hẹn lại sớm |
| V4 | Import theo Unit (`import-unit`, `units`, `units/words`) | Từ của Unit được thêm, không trùng lặp |
| V5 | Wordlist (4k từ): xem coverage, `text-coverage`, `add` | Hiển thị % từ đã biết; thêm từ chưa biết vào sổ |
| V6 | Chủ đề (`topics`, `topics/{id}/add`) | Thêm trọn bộ từ theo chủ đề |
| V7 | Confusables quiz (cặp từ dễ nhầm) → nộp | Chấm đúng/sai, hiện giải thích khác biệt |
| V8 | Word family | Hiện các dạng từ (danh/động/tính/trạng) |
| V9 | Check sentence (đặt câu với từ) | AI nhận xét câu dùng từ đúng/sai và gợi ý sửa |
| V10 | Mnemonics: xem, đăng, vote, báo cáo, xóa của mình | Vote cộng/trừ đúng, không vote trùng; chỉ xóa được bài của mình |
| V11 | Spaced Repetition modal | Mở/đóng được, tiến độ cập nhật sau mỗi thẻ |

Test tự động: `test_reading_*.py`, `test_rearrange*.py`, `test_adapt_text.py`, `test_vocab*.py`, `test_wordlists.py`, `test_confusables.py`, `test_unit_import.py`, `test_mnemonics.py`.

---

## 5. Listening & Movies

| # | Cách test | Kết quả mong đợi |
|---|---|---|
| L1 | Tạo podcast từ chủ đề (`POST /listening/podcasts`) | Sinh transcript + audio TTS; xuất hiện trong danh sách; phát được audio |
| L2 | Xem transcript | Hiển thị đủ nội dung, khớp audio |
| L3 | Comprehension quiz → nộp | Có điểm và đáp án |
| L4 | Dictation (chép chính tả): nghe → gõ → nộp | Chấm theo từng từ, tô màu đúng/sai, tính phần trăm |
| L5 | Dictation gõ rỗng / sai hoàn toàn | Điểm 0, không lỗi |
| L6 | Movie Context: tìm theo từ/cụm (`/movie-context/search`) | Trả các câu ví dụ có audio (TTS fallback) và phụ đề |
| L7 | Lưu 1 kết quả (`matches/{id}/save`) | Lưu thành công, xem lại được |
| L8 | Phát video/overlay (VideoPlayerOverlay), phụ đề chạy theo | Phụ đề khớp thời gian, đóng overlay dừng phát |
| L9 | Lịch sử quiz (`/listening/quizzes`) | Liệt kê các lần làm trước |

Test tự động: `test_listening_*.py`, `test_dictation_grading.py`, `test_movie_context_integration.py`, `test_subtitles.py`.

---

## 6. Speaking Studio

| # | Cách test | Kết quả mong đợi |
|---|---|---|
| S1 | Xem danh sách kịch bản (`/speaking/scenarios`) | Hiển thị các tình huống hội thoại |
| S2 | Bắt đầu phiên, ghi âm 1 lượt, gửi | Nhận: transcript, phản hồi AI dạng chữ + audio TTS, điểm ý định/lịch sự, gợi ý slang/cụm thoại |
| S3 | Chọn provider Gemini / Ollama trong UI | Cả hai trả lời được (Ollama chậm hơn) |
| S4 | Azure STT lỗi (giả lập) | Tự fallback Whisper; lượt hội thoại ghi `stt_provider_used = whisper` |
| S5 | Xem lại phiên (`/sessions/{id}`) và nghe lại audio từng lượt | Đủ các lượt theo thứ tự |
| S6 | Slang & Phrasebook: xem slang, lưu cụm vào sổ | Cụm lưu hiện trong `/speaking/phrasebook` |
| S7 | IELTS Speaking: `exam` → trả lời từng câu (`answer`) → `estimate` | Có đề, có band ước tính; lịch sử ở `ielts/attempts` |
| S8 | Pronunciation: chọn câu, nghe mẫu, ghi âm, chấm (`assess`) | Điểm tổng + điểm từng từ/âm vị; thiếu điểm thành phần không làm lỗi |
| S9 | Pronunciation pairs (cặp âm tối thiểu): `pairs/quiz` → `pairs/check` | Chấm đúng/sai cặp |
| S10 | Silent practice (`silent/prompt`, `silent`) | Nhận gợi ý và phản hồi cho bài nói |
| S11 | Từ chối micro / không có audio | Thông báo rõ ràng, không treo |

Test tự động: `test_speaking_integration.py`, `test_ielts_speaking.py`, `test_pronunciation*.py`, `test_speech_service_azure.py`, `test_phrasebook_fallback_audio_integration.py`.

---

## 7. Writing Lab

| # | Cách test | Kết quả mong đợi |
|---|---|---|
| W1 | Viết tóm tắt tài liệu (`document_summary`) → nộp | Chấm theo độ phủ ý chính của tài liệu, có nhận xét |
| W2 | Đề mở rộng (`extended_topic`) | Điểm 4 tiêu chí: Task Response, Coherence & Cohesion, Lexical Resource, Grammatical Range & Accuracy |
| W3 | Đề tự do + phong cách chứng chỉ (`free_topic`, TOEIC/IELTS/Cambridge) | Dùng chung rubric 4 tiêu chí |
| W4 | Gợi ý đề (`prompts/suggest`) | Trả đề phù hợp phong cách đã chọn |
| W5 | Inline grammar check (`grammar-check`) | Gạch lỗi + gợi ý sửa; lỗi ghi vào nhật ký |
| W6 | Rephrase (`rephrase`) | Trả các cách diễn đạt khác giữ nghĩa |
| W7 | Structures report (`submissions/{id}/structures`) | Liệt kê cấu trúc ngữ pháp đã dùng |
| W8 | Bài có `coherence_cohesion < 60` | Tự ghi lỗi `writing_coherence` vào nhật ký lỗi |
| W9 | Paraphrase bank → check | Chấm câu paraphrase của user so với mẫu |
| W10 | Rearrange the block (Writing) | Giống R5 |
| W11 | Nộp bài rỗng / quá ngắn | Bị từ chối kèm thông báo |

Test tự động: `test_writing_integration.py`, `test_paraphrase_bank.py`, `test_rearrange*.py`.

---

## 8. Ngữ pháp, TOEIC & IELTS

| # | Cách test | Kết quả mong đợi |
|---|---|---|
| G1 | Grammar quiz (`/grammar/quiz`) → `submit` | Có điểm, giải thích từng câu; lượt làm ở `attempts` |
| G2 | Grammar Daily (`/grammar/daily`) | Mỗi ngày một bộ; làm xong không cho nhận lại cùng ngày (nếu có giới hạn) |
| T1 | TOEIC Practice (`/toeic/practice`) theo Part | Sinh đề đúng Part; Part 1 hiển thị đúng ảnh (`part1/images`) |
| T2 | TOEIC Mock (`/toeic/mock`) với CountdownTimer | Hết giờ tự nộp; nộp xong có điểm quy đổi |
| T3 | `GET /toeic/summary` | Tổng hợp kết quả các lần làm |
| T4 | Exam goal card | Đặt mục tiêu điểm, hiển thị khoảng cách tới mục tiêu |
| I1 | IELTS Panel | Xem mục S7 |

Test tự động: `test_grammar.py`, `test_toeic.py`.

---

## 9. Tính năng xã hội & lớp học

| # | Cách test | Kết quả mong đợi |
|---|---|---|
| C1 | Giáo viên tạo lớp (`POST /classes`) | Có mã tham gia |
| C2 | Học viên nhập mã (`/classes/join`) | Vào lớp; sai mã → báo lỗi |
| C3 | Giao bài (`assignments`), xóa bài giao | Học viên thấy / không còn thấy bài |
| C4 | Xóa thành viên / xóa lớp | Chỉ chủ lớp làm được; người khác nhận 403/404 |
| F1 | Bạn bè (`/friends`): kết bạn, xem bảng xếp hạng/cộng đồng (CommunityCard) | Danh sách và xếp hạng đúng |
| D1 | Voice Diary (`/diary`): ghi âm nhật ký | Lưu và xem lại được |

Test tự động: `test_social_class.py`.

---

## 10. Browser Extension

| # | Cách test | Kết quả mong đợi |
|---|---|---|
| E1 | Nạp thư mục `extension` vào Chrome (chế độ nhà phát triển) | Cài thành công, hiện icon |
| E2 | Đăng nhập qua popup | Nhận token `client_type = extension` |
| E3 | Bôi đen/hover 1 từ trên trang web | Hiện nghĩa; có nút lưu từ (kèm `source_url`) vào sổ từ |
| E4 | Dùng token extension gọi route web khác (vd. `/api/writing/...`) | Bị từ chối — chỉ cho phép `/api/extension/*`, `/api/reading/lookup`, `/api/vocab` |

Test tự động: `test_extension_scope.py`.

---

## 11. Kiểm tra giao diện chung

| # | Cách test | Kết quả mong đợi |
|---|---|---|
| U1 | Chuyển lần lượt 7 mục sidebar | Mỗi mục tải được, không lỗi console |
| U2 | Thu nhỏ cửa sổ / mở trên điện thoại | Bố cục không vỡ, dùng được |
| U3 | Tắt backend rồi thao tác | Hiện thông báo lỗi kết nối, không trắng trang |
| U4 | Chức năng cần AI đang chạy | Hiện trạng thái chờ (AiWait), có thể hủy nếu hỗ trợ |
| U5 | Tính năng bị khóa (LockedFeature) | Hiện thông báo yêu cầu mở khóa thay vì lỗi |
| U6 | Animation (CatMascot, TiltCard, CountUp) | Mượt, không gây giật hoặc tràn bố cục |

---

## 12. Bảng ghi kết quả (điền khi test)

| Chức năng | Ngày | Người test | Đạt / Không đạt | Ghi chú lỗi |
|---|---|---|---|---|
| | | | | |
