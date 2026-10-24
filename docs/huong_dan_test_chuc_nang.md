# Hướng dẫn test từng chức năng & kết quả mong đợi — Lumina

Tài liệu test thủ công qua giao diện web, kèm lệnh test tự động. Mỗi dòng ghi rõ **nhấn nút nào** (tên nút viết đúng như trên màn hình, trong dấu ngoặc kép) và **kết quả đúng là gì**. Test case chi tiết theo spec ở backend xem thêm `test-cases (1).md`; test người dùng cuối xem `kiem_thu_nguoi_dung.md`.

Cập nhật: 22/10/2026 (giao diện mới: header lớn hơn, sidebar thu gọn được, đăng nhập Google, Live captions).

## 0. Chuẩn bị môi trường

| Bước | Lệnh / thao tác | Kết quả mong đợi |
|---|---|---|
| 1 | Mở Docker Desktop | `lumina_db`, `lumina_api` (cổng 8000), `lumina_web`, `lumina_tunnel` ở trạng thái Up |
| 2 | Chạy web: `cd frontend-reference && npm run dev` (hoặc dùng bản Docker) | Web mở được tại http://localhost:3000 |
| 3 | Mở http://localhost:8000/docs | Thấy Swagger UI với các nhóm: auth, users, vocab, reading, listening, writing, speaking, toeic, grammar, adaptive, activity, gamification, classes, friends, diary, extension, movie-context, pronunciation |
| 4 | Sau khi sửa code backend: `docker restart lumina_api` | API khởi động lại, code mới có hiệu lực (`--reload` trên Windows không đáng tin) |
| 5 | Sau khi sửa code frontend để Docker dùng bản mới: `docker compose -f docker-compose.yml -f docker-compose.public.yml up -d --build --no-deps web` | `lumina_web` được tạo lại. Phải có `--no-deps`, nếu không compose sẽ build luôn `api` và lỗi do thư mục model whisper |
| 6 | Link tunnel hiện tại: `docker logs lumina_tunnel` rồi tìm dòng `https://….trycloudflare.com` | Mỗi lần tạo lại tunnel là một link mới. Link mới phải dán lại vào extension |
| 7 | Migration (nếu có): `docker exec lumina_api alembic upgrade head` | Không lỗi, DB lên bản mới nhất |

**Lưu ý chung**
- LLM mặc định là Ollama (chạy local, chậm 30–80 giây/bài). Chỉ chọn Gemini ở Speaking/Chat khi cần. Lỗi `ai_quota_exceeded` hoặc 429 khi chạy nhiều test liên tiếp là do quota/rate-limit, không phải bug.
- Cần đăng nhập cho mọi chức năng bên dưới (trừ mục 1). Khi chưa đăng nhập, các tab ngoài Dashboard hiện biểu tượng ổ khóa trong sidebar.
- Mọi chức năng AI thất bại phải hiện **thông báo lỗi dễ hiểu** (khung ErrorNotice có nút thử lại), không được trắng trang.
- Trong lúc AI đang chạy, nút chính đổi sang chữ đang xử lý (ví dụ "Generating...", "Analyzing Essay...", "Processing...") và bị khóa để không bấm trùng.

### Chạy test tự động

Backend (chạy từng file một để tránh rate-limit đăng ký 429 và quota Gemini):

```bash
MSYS_NO_PATHCONV=1 docker exec lumina_api python -m pytest tests/<file>.py -q -p no:warnings
```
- Kỳ vọng: `N passed`. Ngoại lệ đã biết: `test_vocab.py::test_health_check` fail do biến môi trường `production` (không liên quan); `test_speech_service_azure.py::test_stt_roundtrip_returns_text_and_word_timestamps` có thể fail vì Whisper nghe "Gustave" thành "Gustav" (sai lệch nhận dạng giọng nói, không phải lỗi code).
- Chạy cả bộ cùng lúc mất khoảng 18 phút vì nhiều test gọi DB thật và dịch vụ AI.
- Test mới cho đăng nhập Google: `tests/test_auth_google.py` (4 test, không gọi mạng).

Frontend: `cd frontend-reference && npx vitest run` → kỳ vọng 4 file, 34 test pass. Kiểm tra kiểu: `npx tsc --noEmit` → không in lỗi nào.

---

## 1. Đăng nhập & tài khoản

Cửa sổ đăng nhập mở bằng nút **"Connect"** ở header (khi chưa đăng nhập) hoặc ô **"Sign in"** dưới cùng sidebar. Cửa sổ có hai tab **"Log in"** và **"Register"**.

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| 1.1 | Nhấn **"Connect"** | Hiện cửa sổ "Welcome back" ("Connect your Lumina account to continue."). Nhấn **X** hoặc phím Esc thì đóng |
| 1.2 | Tab **"Register"** → nhập email + mật khẩu ≥ 8 ký tự → nhấn **"Register and connect"** | Cửa sổ đóng, vào ứng dụng đã đăng nhập; tên email hiện ở dưới sidebar, nút "Connect" biến mất. Khi gõ mật khẩu có thanh độ mạnh (Too short / Weak / Fair / Good / Strong) |
| 1.3 | Đăng ký lại bằng email đã có | Báo lỗi email đã tồn tại, không tạo thêm tài khoản |
| 1.4 | Tab **"Log in"** → nhập đúng → nhấn **"Log in"** | Cửa sổ đóng, Dashboard hiện lời chào "Good morning/afternoon/evening, <tên>" |
| 1.5 | Đăng nhập sai mật khẩu → **"Log in"** | Ô đỏ rung nhẹ: "Wrong email or password. Please try again." (không tiết lộ email có tồn tại hay không) |
| 1.6 | Nhấn biểu tượng con mắt trong ô mật khẩu | Mật khẩu chuyển giữa dạng ẩn và hiện |
| 1.7 | **"Forgot password?"** → nhập email → **"Send code"** | Hiện ô xanh "If that email has an account, we sent a 6-digit code to it." và hai ô mới: mã 6 số, mật khẩu mới |
| 1.8 | Nhập mã + mật khẩu mới → **"Update password"** | Quay về màn đăng nhập với thông báo "Password updated. Log in with your new password."; mật khẩu cũ không còn dùng được |
| 1.9 | Nhập sai mã → **"Update password"** hoặc **"Verify and log in"** | "That code is wrong or has expired. Use "Resend code" to get a new one." Nhấn **"Resend code"** → "New code sent." |
| 1.10 | **"Back to log in"** ở các màn quên mật khẩu/xác minh | Về lại màn "Welcome back" |
| 1.11 | Nút **"Continue with Google"** (nằm dưới nút Log in, sau dòng "or") | Chỉ hiện khi `GOOGLE_CLIENT_ID` đã cấu hình trong `backend/.env`. Chưa cấu hình thì **không có** nút này và đăng nhập mật khẩu vẫn dùng bình thường |
| 1.12 | Có `GOOGLE_CLIENT_ID`, nhấn **"Continue with Google"** → chọn tài khoản Gmail | Cửa sổ đóng, đăng nhập luôn không cần mã OTP; email trong sidebar đúng Gmail đã chọn. Lần đầu sẽ tự tạo tài khoản mới |
| 1.13 | Bật `REQUIRE_GOOGLE_FOR_GMAIL=true`, đăng nhập mật khẩu bằng email `@gmail.com` | Báo "Gmail addresses must sign in with Google. Use the Continue with Google button." Email không phải Gmail vẫn đăng nhập mật khẩu được |
| 1.14 | Dùng Google qua link tunnel | Nút Google báo lỗi origin vì link tunnel đổi mỗi lần và chưa khai báo ở Google Cloud. Đây là hạn chế đã biết; test ở http://localhost:3000 |
| 1.15 | Bấm ô tài khoản dưới sidebar → **"Log out"** | Về trạng thái chưa đăng nhập: sidebar hiện ổ khóa ở các tab, nút "Connect" xuất hiện lại |
| 1.16 | Gọi API không kèm token (vd. `GET /api/users/me`) | 401 |
| 1.17 | User A mở tài nguyên (document, bài viết…) của user B bằng API | 404 (không phải 403) |
| 1.18 | Đăng nhập/đăng ký liên tục nhiều lần | Sau ngưỡng bị chặn 429 (rate limit) |

Ghi chú: mặc định `REQUIRE_EMAIL_VERIFICATION=false` nên đăng ký xong vào luôn, không hỏi mã. Bật `true` thì sau "Register and connect" sẽ hiện màn "Verify your email" yêu cầu mã 6 số.

Test tự động: `test_auth_integration.py`, `test_auth_rate_limit.py`, `test_auth_google.py`.

---

## 2. Khung giao diện chung: header & sidebar

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| 2.1 | Nhìn thanh header trên cùng | Cao 80px: tiêu đề tab bên trái, ô tìm kiếm ("Search idioms, grammar, stories..."), chip streak, chip bông tuyết (freeze), chip XP kèm huy hiệu "Lv N", chuông thông báo. Chữ đọc rõ, không bị cắt |
| 2.2 | Chip ngọn lửa (vd. "7 days") | Số ngày bằng streak thật. Ngọn lửa sáng khi hôm nay đã học, mờ khi chưa. Nhấn vào chip thì mở màn ôn thẻ |
| 2.3 | Chip bông tuyết | Hiện số freeze còn lại (0–2). Khi streak vừa đứt và có thể khôi phục, chip đổi thành chữ "Restore" màu vàng |
| 2.4 | Rê chuột vào chip XP | Tooltip "x / y XP to level N" |
| 2.5 | Nhấn nút **thu gọn** (biểu tượng ô vuông có mũi tên, góc phải phần logo Lumina) | Sidebar co từ 256px còn 72px: chỉ còn icon; mất chữ Lumina/PRO, nhãn tab, huy hiệu AI/B2/Live, thẻ "cards due" co thành icon lửa có số tròn đen ở góc, phần tài khoản chỉ còn avatar. Nội dung trang giãn rộng ra |
| 2.6 | Khi đã thu gọn, rê chuột vào từng icon | Tooltip đúng tên tab (Dashboard, Knowledge Space…) |
| 2.7 | Khi đã thu gọn, nhấn icon một tab | Chuyển tab bình thường, icon tab hiện tại có nền xanh thông |
| 2.8 | Nhấn nút **mở rộng** (hiện ngay dưới logo khi đang thu gọn) | Sidebar trở lại 256px đầy đủ chữ |
| 2.9 | Tải lại trang (F5) khi đang thu gọn | Sidebar vẫn thu gọn (trạng thái được nhớ) |
| 2.10 | Thu nhỏ cửa sổ dưới 768px | Sidebar ẩn; nút ba gạch (**"Open navigation menu"**) ở header mở sidebar dạng ngăn kéo luôn ở dạng đầy đủ |
| 2.11 | Nhấn thẻ vàng **"Start quick review"** (sidebar) | Mở màn ôn thẻ (xem mục 3.2) |
| 2.12 | Gõ vào ô tìm kiếm ở header | Danh sách tài liệu/nội dung lọc theo từ khóa ở các tab có hỗ trợ tìm |

---

## 3. Dashboard & ôn thẻ

### 3.1 Dashboard

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| 3.1.1 | Mở tab **Dashboard** với tài khoản mới | Banner xanh thông: lời chào theo giờ + tên (phần trước @ của email; tên dài thì chữ nhỏ lại và cắt gọn "…"). Streak 0, "No activity yet — finish a lesson in any skill to see it here.", không lỗi |
| 3.1.2 | Nhấn **"Start review · N cards"** (nút vàng) | Mở màn ôn thẻ với N thẻ đến hạn |
| 3.1.3 | Nhấn **"Speaking warm-up"** | Chuyển sang tab Speaking Studio |
| 3.1.4 | Nhấn con mèo hoặc chọn nhân vật (3 nút tròn dưới mèo: Sir Whiskers, Bad Kitty, Chill Buddy) | Mèo đổi nhân vật, hiện bong bóng thoại ngắn |
| 3.1.5 | Thẻ **Current streak** | Số ngày + "goal 30"; lưới 30 ô: ô các ngày đã học tô màu cam, ô hôm nay có viền. Dòng "Longest streak" và "Freezes: n (a new one every 7-day streak, max 2)" |
| 3.1.6 | Nhấn **"Launch flashcards"** (thẻ Memory review queue) | Mở màn ôn thẻ; số trong thẻ bằng số thẻ đến hạn |
| 3.1.7 | Thẻ **Overall mastery** | Vòng tròn % và nhãn CEFR; chưa có dữ liệu thì hiện "—" và "No level yet". Nhấn **"View skill radar"** → sang tab Adaptive Progress |
| 3.1.8 | Nhấn **"Turn on timer mode"** (khối "This week, in minutes") | Nhãn đổi thành "Timer mode on"; từ nay bộ đếm giờ mới tính phút học cho từng kỹ năng, thanh phân bổ và 4 mục Reading/Listening/Writing/Speaking cập nhật |
| 3.1.9 | Nhấn **"All materials"** (cạnh "Pick up where you left off") | Chuyển sang Knowledge Space |
| 3.1.10 | Nhấn một thẻ hoạt động gần đây | Chuyển tới tab kỹ năng tương ứng; thẻ có điểm thì hiện % và thanh tiến độ |
| 3.1.11 | Khối **Daily grammar lesson**: nhấn **"Open Grammar map"** | Chuyển sang Writing Lab, đến phần Grammar map. Nếu hôm nay đã làm thì thay bằng chữ "Done for today. Nice work." và tag "Done" |
| 3.1.12 | **"Remind me at"** chọn một giờ | Trình duyệt hỏi quyền thông báo; chọn "Off" thì tắt nhắc. Ghi chú nhỏ: chỉ nhắc khi tab Lumina đang mở |
| 3.1.13 | Khối **IELTS goal & daily plan**: chọn "Target band", chọn "Exam date", nhấn **"Save goal"** | Hiện "N days to go · … · M min/day" và danh sách việc cần làm mỗi ngày. Lỗi mạng thì hiện "Could not reach the server — try again." |
| 3.1.14 | Khối **Friends & classes** (2 cột): nhập email bạn → **"Invite"** | Hiện thông báo kết quả; bảng xếp hạng bên dưới có huy hiệu hạng (hạng 1 màu vàng), dòng của mình tô nền xanh và có "(you)". Nhấn **"This week"/"All time"** đổi XP hiển thị |
| 3.1.15 | Bên phải: nhập "New class name" → **"Create (I'm the teacher)"**; hoặc nhập "Join code" → **"Join"** | Lớp xuất hiện thành nhãn bên dưới (lớp mình dạy có "code …· N students"); mã sai thì hiện lỗi đỏ phía dưới thẻ |

### 3.2 Màn ôn thẻ (Spaced Repetition)

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| 3.2.1 | Mở màn ôn thẻ | Hiện thẻ đầu tiên; có 4 chế độ: **"Flip"**, **"Match meaning"**, **"Spell it"**, **"Listen & type"** |
| 3.2.2 | Chế độ **Flip**: nhấn vào thẻ để lật | Mặt sau hiện nghĩa + ví dụ; xuất hiện 4 nút **"Again"**, **"Hard"**, **"Good"**, **"Easy"** |
| 3.2.3 | Nhấn **"Good"** hoặc **"Easy"** | Sang thẻ kế; thẻ này sẽ hẹn lại xa hơn |
| 3.2.4 | Nhấn **"Again"** | Sang thẻ kế; thẻ này hẹn lại sớm (ngay hôm sau) |
| 3.2.5 | Chế độ **Match meaning** chọn đáp án đúng | Hiện "Correct!"; chọn sai hiện "Not quite." và đáp án đúng được tô |
| 3.2.6 | Chế độ **Spell it** gõ đúng từ / **Listen & type** nghe rồi gõ | Đúng: "Correct!"; sai: "Not quite." kèm đáp án |
| 3.2.7 | Nhấn **"Add words from my mistakes"** | Từ bạn từng làm sai được thêm thành thẻ ôn; nếu không có gì mới hiện "No new missed words to add." |
| 3.2.8 | Học hết thẻ, quay lại Dashboard | Số "cards due" giảm; chuỗi hôm nay được tính nếu có ôn |

Test tự động: `test_activity.py`, `test_gamification.py`, `test_streak_freeze.py`, `test_study_plan.py`.

---

## 4. Knowledge Space (Notebook)

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| 4.1 | Mở tab **Knowledge Space** | Tiêu đề "Knowledge Space & Notebook", dòng "Connected to FastAPI backend" màu xanh, danh sách tài liệu bên trái, chi tiết bên phải. Chưa có tài liệu thì hiện "No documents yet" |
| 4.2 | Nhấn **"Add Note or Document"** | Mở hộp "Create New Material or Note" gồm ô Title, ô chọn file "DOCX, DOC or PDF file", ô "Content or Pasted Text", nút **"Cancel"** |
| 4.3 | Chọn file `.docx` rồi lưu | Tài liệu xuất hiện ở đầu danh sách (kèm nhãn DOCX và ngày); xử lý xong thì mở ra xem được nội dung |
| 4.4 | Chọn file không phải .docx/audio (vd. ảnh) | Bị từ chối kèm thông báo; không tạo tài liệu dở |
| 4.5 | Nhấn **"Cancel"** hoặc **X** khi đang upload | Upload dừng, không để lại tài liệu dở |
| 4.6 | Nhấn **"New Folder"**, đặt tên | Thư mục mới hiện thành nút lọc cạnh "All Materials (n)", ví dụ "QA Test Folder (0)" |
| 4.7 | Nhấn một nút thư mục/"All Materials" | Danh sách chỉ còn tài liệu thuộc thư mục đó; số trong ngoặc đúng |
| 4.8 | Gõ vào ô **"Filter by folder or tag..."** | Danh sách lọc theo chữ gõ |
| 4.9 | Nhấn một tài liệu trong danh sách | Bên phải hiện tên, nhãn loại, tab **"Content"** và **"Chat"** |
| 4.10 | Tab **"Content"** | Hộp **"AI Summary"** (tóm tắt tiếng Anh + các câu hỏi gợi ý) và phần nội dung tài liệu **cuộn trong khung riêng** (cao tối đa 60% màn hình), trang không bị dài vô tận |
| 4.11 | Nhấn **"Regenerate"** ở AI Summary | Tạo lại tóm tắt; lần mở sau dùng lại bản đã lưu, không sinh lại |
| 4.12 | Gõ vào **"Search in this document..."** | Chỉ còn các đoạn chứa từ khóa, từ khóa được tô nổi; hiện "n / m paragraphs". Không khớp thì "No paragraph matches …" |
| 4.13 | Nhấn **ngôi sao** (Toggle star) | Tài liệu được gắn sao; tải lại vẫn còn |
| 4.14 | Tab **"Chat"** → gõ câu hỏi có trong tài liệu → nhấn **"Send message"** (hoặc Enter) | Hiện "Thinking..." rồi câu trả lời bám nội dung tài liệu, kèm trích dẫn; tải lại trang vẫn còn lịch sử |
| 4.15 | Chat: hỏi câu ngoài tài liệu | Trả lời rằng không tìm thấy trong tài liệu, không bịa |
| 4.16 | Chat: đổi ô **"Chat model"** (Gemini / Ollama (local)) và **"Chat personality"** (Polite / Rebel / Buddy) | Câu trả lời tiếp theo đổi giọng điệu theo nhân vật; Ollama chậm hơn |
| 4.17 | Nhấn **"Export"**, **"Share"**, **"Delete"** | Export tải file; Share sao chép liên kết/nội dung; Delete xóa tài liệu khỏi danh sách (chunk liên quan bị xóa theo) |
| 4.18 | Animation bóng rổ ở nút upload | Khi upload bóng bay vào rổ (thành công) hoặc trượt (lỗi); không treo giao diện |

Test tự động: `test_notebook_integration.py`, `test_notebook_chat_integration.py`, `test_chunking.py`, `test_rag_local_pipeline.py`.

---

## 5. Reading & Vocabulary

Góc trên bên phải của mọi tab kỹ năng có **đồng hồ đếm ngược** (vd. "04:00" với nút Play/Pause và mũi tên chọn thời lượng). Nhấn **Play** → đồng hồ chạy, chuyển tab khác bị khóa ("timer lock") cho tới khi dừng hoặc hết giờ. Nhấn **Pause** hoặc **Restart** (sau khi hết giờ) để dừng/chạy lại.

### 5.1 Reading

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| R1 | Mở tab **Reading & Vocab** | Có sẵn một bài đọc B2 kèm các từ mục tiêu được tô sáng, ô "Comprehension Check", dòng "6 Target Words" |
| R2 | Nhấn một từ được tô (vd. "pervasive") | Cột phải hiện: loại từ, phiên âm, "Definition & meaning", câu trong bài ("Used in the article"), Synonyms/Antonyms, "Guess the Context Challenge" và danh sách "Other Target Words in Passage" |
| R3 | Nhấn nút loa (Audio Pronunciation) | Phát phát âm của từ |
| R4 | Nhấn nút bookmark (Save to Notebook) | Từ được lưu vào sổ từ; tải lại vẫn còn; lưu lỗi thì hiện "Vocabulary save failed" |
| R5 | Ở "Guess the Context Challenge", chọn một đáp án | Đáp án đúng được tô xanh, sai tô đỏ kèm phản hồi |
| R6 | Nhấn **"Start Backend Classic"** | Nút đổi thành "Loading Classic..." rồi hiện bộ câu hỏi từ tài liệu; chọn đáp án cho từng câu |
| R7 | Nhấn **"Submit Classic answers"** | Hiện điểm, câu đúng/sai và giải thích; câu sai được ghi vào nhật ký lỗi (sẽ thấy ở Adaptive Progress) |
| R8 | Nhấn **"Skim & Scan"** | Mở hộp "New Skim & Scan Passage": chọn "Passage source" (**"My document"** hoặc **"AI topic"**), chủ đề, "CEFR Target Level", "Question type". Nếu chưa có tài liệu sẵn sàng hiện "No ready document yet — upload a .docx in Knowledge Space first…" |
| R9 | Nhấn **"Generate Passage"** | Nút đổi thành "Generating..."; xong thì hiện bài đọc mới (nguồn "From your document" nếu chọn My document) cùng câu hỏi; **"Cancel"** để đóng hộp |
| R10 | Nhấn **"Start exercise"** ở khối "Rearrange the paragraph" | Hiện các khối câu xáo trộn; kéo để sắp xếp |
| R11 | Nhấn **"Check order"** | Điểm tính theo tỷ lệ khối đúng vị trí (chấm một phần); khối đúng tô xanh. **"Try again"/"Check again"/"New exercise"** cho làm lại |
| R12 | Khối **Adapt an article to your level**: dán văn bản, chọn mức (vd. B1), nhấn **"Rewrite"** | Văn bản được viết lại đúng mức độ, giữ ý chính |
| R13 | Rê chuột vào từ bất kỳ trong bài (tra nhanh) | Hộp nhỏ hiện nghĩa và phiên âm kèm nút lưu từ |

### 5.2 Vocabulary (các khối công cụ bên dưới bài đọc, mỗi khối là một thẻ riêng)

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| V1 | **Guess the context**: nhập một từ → nhấn **"Challenge me"** | Hiện câu có chỗ trống và các lựa chọn; chọn xong hiện "Correct!" hoặc "Not quite — the right answer is highlighted." |
| V2 | **Story from your words**: nhấn **"Pick words to review"**, chọn tối đa 15 từ, tạo truyện | Truyện ngắn có dùng các từ đã chọn |
| V3 | **Use it in a sentence**: nhấn **"Pick a word"**, đặt câu | Nhận xét "Word used correctly" hoặc "Check the word's meaning" kèm gợi ý sửa; có thể xem mẹo nhớ từ |
| V4 | Mnemonic: nhấn **"Share my tip"** (hoặc **"Replace my tip"**) | Mẹo của bạn hiện trong danh sách; vote cộng/trừ đúng và không vote trùng; chỉ xóa được mẹo của mình; báo cáo thì mẹo bị ẩn với bạn |
| V5 | **Confusing word pairs**: nhấn **"Start 8 questions"** → chọn đáp án → **"Check answers"** | Hiện "Score: x/8"; câu sai có giải thích tiếng Việt và so sánh "Tiếng Việt vs English"; **"Try another set"** để làm bộ mới |
| V6 | **Exam word lists**: nhấn tab **"IELTS academic (NAWL)"** hoặc **"TOEIC (TSL)"** | Hiện "You have saved n of N words (x%)" và thanh tiến độ; danh sách "Words to learn next" |
| V7 | Nhấn một từ "+ …" ở "Words to learn next" | Từ được thêm vào sổ; số "saved" tăng |
| V8 | Dán đoạn văn vào ô, nhấn **"Check coverage"** | Hiện % từ trong đoạn thuộc danh sách thi |
| V9 | **Import a textbook unit**: nhập tên unit, dán danh sách từ, nhấn **"Add unit words"** | Từ được thêm; unit xuất hiện ở "My units"; không trùng từ cũ |
| V10 | **Words by topic**: chọn một chủ đề (vd. "Cities & Urban Life (0/23)") | Thêm trọn bộ từ của chủ đề; số "(x/23)" tăng. Ô tìm chủ đề/từ lọc theo chữ gõ |

Test tự động: `test_reading_*.py`, `test_rearrange*.py`, `test_adapt_text.py`, `test_vocab*.py`, `test_wordlists.py`, `test_confusables.py`, `test_unit_import.py`, `test_mnemonics.py`.

---

## 6. Listening & Movies

Tab có hai nút chuyển: **"AI Podcast & Dictation"** và **"Movie Context Finder"**.

### 6.1 AI Podcast & Dictation

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| L1 | Mở **AI Podcast & Dictation** | Cột trái: thẻ "New podcast" (ô chọn tài liệu + nút **"Generate podcast"**) và danh sách "My podcasts". Cột phải ghi "Select or generate a podcast to start listening." |
| L2 | Chưa có tài liệu | Thẻ "New podcast" ghi "Upload a .docx or audio file in Knowledge Space first." |
| L3 | Chọn tài liệu, nhấn **"Generate podcast"** | Hiện "Generating audio & transcript..." (chậm); xong podcast xuất hiện đầu "My podcasts" kèm thời lượng |
| L4 | Nhấn một podcast trong "My podcasts" | Cột phải hiện trình phát, bảng chọn **"Speed"** và transcript; từ đang đọc được tô theo thời gian |
| L5 | Nhấn một từ trong transcript | Hiện nghĩa ("Looking up..." rồi kết quả); tra lỗi thì "Could not look this word up." |
| L6 | **Comprehension quiz**: nhấn **"Generate questions"** → chọn đáp án → nộp | Có điểm; đáp án đúng, "Trap:" (đáp án bẫy) và đoạn căn cứ được tô trong transcript; nhấn **"▶ Play this part"** nghe lại đoạn đó. **"New questions"** tạo bộ mới; "Past quizzes" liệt kê các lần trước |
| L7 | **Dictation**: nhấn **"Start dictation"** | Phát một đoạn ngắn, hiện ô "Type what you hear..." |
| L8 | Gõ lại đoạn vừa nghe, nhấn **"Check answer"** | Chấm theo từng từ, từ đúng/sai tô màu khác nhau, hiện phần trăm; gõ hoàn hảo hiện "Perfect — no mistakes!". **"New segment"** sang đoạn khác |
| L9 | Nhấn **"Check answer"** khi ô trống | Điểm 0, không lỗi |

### 6.2 Movie Context Finder

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| L10 | Gõ cụm từ (vd. "piece of cake") hoặc chọn từ gợi ý ở "Popular:" → nhấn **"Find lines"** | Hiện "Writing lines and recording them — this takes a few seconds..." rồi danh sách câu ví dụ có phụ đề |
| L11 | Nhấn **"Listen"** ở một kết quả | Phát audio câu đó; nút đổi thành **"Stop"** |
| L12 | Nhấn **"Watch scene"** | Mở lớp phủ video có phụ đề chạy khớp thời gian; có nhãn "Film clip" hoặc "Simulated demo scene — AI voices, not a real movie". Đóng lớp phủ thì dừng phát |
| L13 | Nhấn **"Save line"** (hoặc **"Save scene"** trong video) | Nút đổi thành **"Saved"**; mục đã lưu xem lại được |

### 6.3 TOEIC-style practice (cuối tab Listening)

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| T1 | Nhấn **"Part 5 · Incomplete sentences"** (hoặc Part 1, 2, 3, 4, 6, 7) | Sinh đề đúng Part đó; ô "Quick set" được tick thì chỉ làm bộ ngắn ~2 phút |
| T2 | Part 1 · Photographs | Hiển thị đúng ảnh minh họa cho từng câu |
| T3 | Chọn đáp án rồi nộp | Có điểm, đáp án đúng, giải thích; kết quả được tổng hợp trong `GET /toeic/summary` |
| T4 | Nhấn **"Full mock test (Part 1–7, one timer)"** | Làm trọn bộ với một đồng hồ chung; hết giờ hiện "Time's up" và tự nộp; có điểm quy đổi |

Test tự động: `test_listening_*.py`, `test_dictation_grading.py`, `test_movie_context_integration.py`, `test_subtitles.py`, `test_toeic.py`.

---

## 7. Speaking Studio

Tab có 5 nút chuyển: **"Conversation practice"**, **"Live call"**, **"Live captions"**, **"IELTS mock test"**, **"Pronunciation lab"**.

### 7.1 Conversation practice

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| S1 | Mở **Conversation practice** | Mèo 3D với bong bóng "Hi! Pick a scene and start a session, then tap the mic and talk to me."; nút mic mờ, ghi "Start a session first"; bên phải có thẻ "Latest turn feedback" trống và khối Slang library |
| S2 | Chọn nhân vật (Sir Whiskers / Bad Kitty / Chill Buddy) | Khung nhân vật đổi viền xanh, màu nền mèo đổi theo |
| S3 | Chọn một tình huống trong danh sách (vd. "Chatting with a new classmate · casual") | Dòng "Goal: …" bên dưới đổi theo tình huống |
| S4 | Chọn "Gemini" hoặc "Ollama" ở ô provider | Cả hai đều trả lời được (Ollama chậm hơn) |
| S5 | Nhấn **"Start session"** | Nút đổi thành **"New session"**; mèo chào; mic sáng lên ghi "Tap the mic and speak" |
| S6 | Nhấn mic (**"Start recording"**) → nói → nhấn lại (**"Stop recording"**) | Ghi "Recording — tap to send", sau đó "Scoring your turn..." rồi "The cat is answering". Kết quả: bong bóng mèo trả lời bằng chữ + giọng nói, thẻ "Latest turn feedback" hiện điểm phát âm, ý định, lịch sự và gợi ý |
| S7 | Nói quá ngắn hoặc im lặng | Mèo nói "I couldn't hear anything. Try speaking a little longer." hoặc "I couldn't make out any words. Please record again." |
| S8 | Từ chối quyền micro | Thông báo rõ ràng, không treo |
| S9 | Ở khối Slang library nhấn biểu tượng bookmark (**"Save phrase"**) | Biểu tượng đổi thành **"Saved"**; cụm xuất hiện ở tab **"My phrasebook (n)"** (số trong ngoặc tăng) |
| S10 | Ô "All levels" | Lọc cụm slang theo mức độ |
| S11 | Azure STT lỗi (giả lập) | Tự chuyển sang Whisper; lượt hội thoại ghi `stt_provider_used = whisper` |

### 7.2 Live call

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| S12 | Nhấn **"Live call"** → **"Start live call"** | Hiện "Connecting..." rồi "Listening. Talk anytime." — không cần bấm ghi, cứ nói |
| S13 | Nói một câu | Mèo trả lời bằng giọng; trong lúc mèo nói hiện "The cat is talking. Just speak to interrupt."; bạn nói chen thì mèo dừng |
| S14 | Nhấn **"Hang up"** | Hiện "Saving your call..." rồi lưu cuộc gọi; có thể xem lại như một phiên |
| S15 | Ollama chưa chạy | "Can't reach Ollama. Make sure it is running on this computer." |
| S16 | Hết phiên đăng nhập | "Your sign-in expired. Please sign in again." |

### 7.3 Live captions

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| S17 | Nhấn **"Live captions"** | Có hai ô chọn nguồn âm thanh: **"Video / tab audio"** và **"Microphone"**; nút chọn kiểu **"Offline captions"** / **"Cloud captions"** |
| S18 | Không chọn nguồn nào, nhấn **"Start captions"** | Báo "Pick at least one audio source." |
| S19 | Chọn nguồn, nhấn **"Start captions"** | Phụ đề tiếng Anh chạy theo thời gian thực kèm bản dịch tiếng Việt; nút đổi thành **"Stop"** |
| S20 | Chế độ **"Cloud captions"** khi server chưa có khóa | "Cloud captions aren't configured on this server." (dùng "Offline captions" thay thế) |
| S21 | Nhấn **"Stop"** | Dừng phụ đề, giữ lại nội dung đã có |

### 7.4 IELTS mock test

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| S22 | Nhấn **"IELTS mock test"** → **"Start test"** | Sinh đề Part 1–3; nút đổi thành **"New test"** |
| S23 | Nhấn **"Record answer"** → nói → **"Stop"** | Hiện "Processing..." rồi câu trả lời được ghi nhận. Không nói gì thì báo "I could not hear any words. Record this question again." |
| S24 | Trả lời hết các câu, nhấn nút ước lượng band | Hiện band ước tính và nhận xét; lịch sử ở `ielts/attempts` |

### 7.5 Pronunciation lab

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| S25 | Nhấn **"Pronunciation lab"**; chọn một nhóm bài ("Final sounds", "Consonant clusters", "Word stress") | Hiện câu mẫu; nghe mẫu rồi **ghi âm** ("Repeat after the model") |
| S26 | Nhấn **"Stop & score"** | Điểm tổng + điểm từng từ/âm; từ yếu được tô; thiếu một điểm thành phần không gây lỗi |
| S27 | Trò chơi cặp âm | Chọn đáp án → "Correct" hoặc báo sai |
| S28 | Silent mode: viết ít hơn 8 từ | Báo "Write at least 8 words, with a few different ones." |
| S29 | Voice diary: nhấn **"Record today's entry"** | Ghi âm xong lưu được và nghe lại được; lỗi quyền micro thì "Could not access the microphone." |

Test tự động: `test_speaking_integration.py`, `test_ielts_speaking.py`, `test_pronunciation*.py`, `test_speech_service_azure.py`, `test_phrasebook_fallback_audio_integration.py`, `test_caption_service.py`, `test_echo_gate.py`.

---

## 8. Writing Lab

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| W1 | Mở **Writing Lab** | Ô "Essay title...", thanh định dạng (B / I / U / danh sách), ô soạn thảo có dòng kẻ, đếm "0 Words • 0 Characters", dòng "Auto-saved to Notebook". Bên phải thẻ "Writing score" với "—" và "Chưa chấm — hãy viết bài rồi bấm Analyze" |
| W2 | Nhấn **"Suggest a topic (uses the title as theme, or IELTS style)"** | Ô tiêu đề/đề bài được điền một đề phù hợp |
| W3 | Viết bài (≥ 30 từ) → nhấn **"Analyze & Correct with AI"** | Nút đổi thành "Analyzing Essay..."; xong thẻ điểm hiện số /100, bên dưới là "Corrections & vocabulary upgrades": các lỗi ngữ pháp kèm cách sửa, gợi ý từ vựng học thuật, điểm 4 tiêu chí (Task Response, Coherence & Cohesion, Lexical Resource, Grammatical Range & Accuracy) |
| W4 | Nhấn **"Analyze & Correct with AI"** khi bài rỗng/quá ngắn | Bị từ chối kèm thông báo (nộp từ 30 từ trở lên) |
| W5 | Nhấn **"Quick grammar check"** | Gạch/tô các lỗi ngay trong bài kèm gợi ý; lỗi được ghi vào nhật ký lỗi |
| W6 | Nhấn **"Rephrase my weakest sentence"** | Hiện vài cách diễn đạt khác giữ nguyên nghĩa |
| W7 | Bài có Coherence & Cohesion < 60 | Tự ghi lỗi `writing_coherence` vào nhật ký lỗi (xem ở Adaptive Progress) |
| W8 | Khối **Rearrange the sentence**: **"Start exercise"** → kéo các cụm → **"Check order"** | Điểm chấm một phần; **"New exercise"** làm bài khác |
| W9 | Khối **Paraphrase bank**: chọn một thẻ (**"Synonyms"**, **"Active ↔ passive"**, **"Change structure"**, **"Nominalisation"**) | Hiện bài tập tương ứng; viết lại câu và nhấn kiểm tra thì được chấm so với mẫu |
| W10 | Khối **Grammar map**: nhấn nút xanh **"3-minute daily lesson (6 questions on your weakest topic)"** | Bộ 6 câu về chủ đề yếu nhất của bạn |
| W11 | Grammar map: nhấn một chủ đề (**"Placement test (all topics)"**, **"Tenses"**, **"Articles"**, **"Prepositions"**, **"Subject–verb agreement"**, **"Word forms (noun/verb/adj/adv)"**, **"Fix the error"**) | Sinh quiz đúng chủ đề; nộp xong có điểm và giải thích từng câu; mục "Past attempts" thêm một dòng (ngày giờ — chủ đề: điểm/tổng) |

Test tự động: `test_writing_integration.py`, `test_paraphrase_bank.py`, `test_rearrange*.py`, `test_grammar.py`.

---

## 9. Adaptive Progress

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| A1 | Mở **Adaptive Progress** | Hàng đầu: thẻ xanh "CEFR level" (vd. B1 Intermediate), Avg. score, Streak (kèm "Done today"/"Not yet today"), XP + Level |
| A2 | Khối **Four-skill mastery** | 4 thanh: Listening Comprehension, Reading & Vocabulary, Writing, Speaking & Pronunciation; kỹ năng chưa làm hiện "Not started" |
| A3 | Dưới đó "Where the mistakes come from" | Thanh chia màu theo loại lỗi, kèm số lượng từng loại |
| A4 | Khối **Error journal**: nhấn **"Learn why"** ở một lỗi | Mở phần giải thích; nhấn lại đổi thành "Hide explanation" |
| A5 | Khối **Review next** | Liệt kê tối đa 6 mục cần ôn, tên đọc được (vd. "Listening comprehension", không còn dạng `listening_comprehension`), kèm nhãn "mistake" hoặc "word" |
| A6 | Khối **Practice your weak spots**: nhấn **"Generate quiz"** | Sinh quiz từ các lỗi gần đây (hoặc ngữ pháp/từ vựng chung nếu chưa có lỗi); nút đổi thành **"New quiz"** |
| A7 | Chọn đáp án → nhấn **"Submit answers"** | Có điểm; câu sai ghi vào nhật ký lỗi; mục Study habits cập nhật |
| A8 | Khối **Study habits** | Active days (30d), Activities / day, Peak hour, Favourite skill, Quiz progress; chưa đủ dữ liệu thì "Take a few quizzes to see your trend" |
| A9 | Streak & freeze | Học mỗi ngày → streak +1; cứ đủ 7 ngày liên tiếp được thêm 1 freeze (tối đa 2). Bỏ 1 ngày mà còn freeze → vẫn giữ streak và trừ 1 freeze; hết freeze thì streak về 0 (có thể khôi phục bằng quiz 10 câu đạt từ 70% trong cùng ngày, hiện thông báo ở thẻ Streak) |

Test tự động: `test_activity.py`, `test_adaptive.py`, `test_gamification.py`, `test_streak_freeze.py`.

---

## 10. Lớp học & bạn bè

| # | Thao tác — nhấn nút nào | Kết quả đúng phải thấy |
|---|---|---|
| C1 | Dashboard → khối Friends & classes: nhập tên lớp, nhấn **"Create (I'm the teacher)"** | Lớp xuất hiện thành nhãn xanh "tên · code XXXXXX · 1 students"; mã tham gia 6–8 ký tự |
| C2 | Tài khoản khác: nhập mã, nhấn **"Join"** | Vào lớp, lớp hiện thành nhãn xám; mã sai thì có lỗi đỏ dưới thẻ |
| C3 | Giáo viên nhấn nhãn lớp, nhập "Assignment title", chọn skill/hạn, nhấn **"Assign"** | Bài giao hiện trong danh sách lớp; học viên thấy "Not done yet", làm xong thấy "✓ Done" (bài có skill tự đánh dấu khi học viên luyện skill đó sau lúc giao) |
| C4 | Giáo viên nhấn **"Delete"** ở bài giao hoặc **"Remove"** ở học viên | Mục biến mất; chỉ chủ lớp làm được, người khác nhận 403/404 |
| C5 | Bảng tiến độ học viên (giáo viên) | Cột Streak, XP, Min/wk, Mistakes, Words, Tasks; phút chỉ tính cho học viên đã bật timer mode |
| F1 | Nhập email bạn, nhấn **"Invite"** | Hiện kết quả lời mời; người nhận thấy "… wants to be friends" với nút **"Accept"** / **"Decline"**; đồng ý xong hai bên thấy nhau trong bảng xếp hạng |

Test tự động: `test_social_class.py`.

---

## 11. Browser Extension

| # | Thao tác | Kết quả đúng phải thấy |
|---|---|---|
| E1 | Chrome → `chrome://extensions` → bật Developer mode → **Load unpacked** (hoặc **Reload**) → chọn thư mục `extension` | Extension xuất hiện trong danh sách, có icon trên thanh công cụ |
| E2 | Mở popup extension, nhập địa chỉ server (link tunnel hiện tại hoặc http://localhost:8000) và đăng nhập | Popup báo đã kết nối; token có `client_type = extension`. Link tunnel đổi mỗi lần tạo lại tunnel, phải dán link mới |
| E3 | Bôi đen hoặc rê chuột vào một từ trên trang web | Hiện nghĩa; có nút lưu từ kèm `source_url` vào sổ từ |
| E4 | Phụ đề trực tiếp trên YouTube | Có phụ đề tiếng Anh chạy theo video kèm dịch tiếng Việt (khi video có phụ đề) |
| E5 | Bật chế độ tab audio trên trang không có phụ đề (vd. Facebook) | Phụ đề được sinh từ âm thanh của tab (Offline dùng Whisper, Cloud dùng Soniox nếu có khóa) |
| E6 | Dùng token extension gọi route web khác (vd. `/api/writing/...`) | Bị từ chối (403) — chỉ cho phép `/api/extension/*`, `/api/reading/lookup`, `/api/vocab` |

Test tự động: `test_extension_scope.py`.

---

## 12. Kiểm tra giao diện chung

| # | Cách test | Kết quả đúng phải thấy |
|---|---|---|
| U1 | Chuyển lần lượt 7 tab trong sidebar | Mỗi tab tải được, tiêu đề header đổi theo tab, không có lỗi đỏ trong console trình duyệt |
| U2 | Thu nhỏ cửa sổ / mở trên điện thoại | Bố cục không vỡ; sidebar thành ngăn kéo; các thẻ xếp thành một cột |
| U3 | Tắt backend (`docker stop lumina_api`) rồi thao tác | Hiện thông báo lỗi kết nối rõ ràng, không trắng trang; bật lại (`docker start lumina_api`) thì dùng tiếp được |
| U4 | Chức năng cần AI đang chạy | Nút chính đổi sang chữ đang xử lý và bị khóa; hiện trạng thái chờ (AiWait) |
| U5 | Tính năng bị khóa (LockedFeature) | Hiện thông báo yêu cầu đăng nhập/mở khóa thay vì lỗi |
| U6 | Animation (mèo, thẻ nghiêng khi rê chuột, số đếm lên) | Mượt, không giật, không tràn bố cục; bật "reduce motion" của hệ điều hành thì chuyển động gần như tắt |
| U7 | Dùng phím Tab trên bàn phím | Mọi nút/ô nhập có viền focus xanh rõ ràng |

---

## 13. Kết quả chạy test tự động gần nhất (22/10/2026)

| Bộ test | Lệnh | Kết quả | Ghi chú |
|---|---|---|---|
| Backend, toàn bộ | `docker compose exec -T api python -m pytest -q -W ignore -x` | **268 passed, 1 failed** (18 phút) | Chạy với `-x` nên dừng ở lỗi đầu tiên; các file test xếp sau `test_speech_service_azure.py` chưa chạy trong lượt này |
| Backend, đăng nhập | `pytest tests/test_auth_google.py tests/test_auth_integration.py` | **13 passed** | Gồm 4 test mới của đăng nhập Google |
| Frontend | `npx vitest run` | **34 passed** (4 file) | |
| Frontend, kiểu | `npx tsc --noEmit` | Không lỗi | |

Test fail duy nhất: `test_speech_service_azure.py::test_stt_roundtrip_returns_text_and_word_timestamps`. Whisper nhận dạng câu mẫu thành "Gustav Eiffel" thay vì "Gustave Eiffel", nên phép kiểm tra `"gustave" in text` sai. Đây là sai lệch nhận dạng giọng nói, không liên quan tới code đăng nhập hay giao diện đã sửa ngày hôm nay.

Chưa kiểm thử được: nút "Continue with Google" với tài khoản Google thật, vì chưa có `GOOGLE_CLIENT_ID`. Phần backend đã được test bằng dữ liệu giả lập.

---

## 14. Bảng ghi kết quả (điền khi test)

| Chức năng | Ngày | Người test | Đạt / Không đạt | Ghi chú lỗi |
|---|---|---|---|---|
| | | | | |
