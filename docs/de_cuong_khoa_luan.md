## 2. Tên đề tài

**Nghiên cứu và xây dựng nền tảng học tiếng Anh ứng dụng trí tuệ nhân tạo (AI-Powered English Learning Platform) tích hợp cá nhân hóa lộ trình học và mô phỏng ngữ cảnh giao tiếp thực tế**

## 3. Lý do chọn đề tài

Hiện nay, các ứng dụng học tiếng Anh phổ biến (Duolingo, ELSA Speak, Cambly...) thường tập trung vào một kỹ năng riêng lẻ (từ vựng, phát âm, hội thoại), thiếu sự liên kết xuyên suốt giữa các kỹ năng Nghe – Nói – Đọc – Viết trên cùng một nguồn tài liệu học tập của người dùng. Bên cạnh đó, phần lớn các ứng dụng chấm điểm dựa trên quy tắc cố định (rule-based), chưa tận dụng được khả năng hiểu ngữ cảnh và cá nhân hóa sâu mà các mô hình ngôn ngữ lớn (LLM) hiện đại có thể mang lại.

Sự phát triển của các công nghệ AI trong vài năm gần đây — mô hình ngôn ngữ lớn (GPT-4o), nhận diện giọng nói (Whisper, Azure Speech), tổng hợp giọng nói (Text-to-Speech đa accent), và cơ sở dữ liệu vector phục vụ truy xuất ngữ nghĩa (RAG) — đã tạo điều kiện kỹ thuật để xây dựng một nền tảng học tập cá nhân hóa sâu hơn: người học có thể tải lên chính tài liệu họ quan tâm (bài báo, giáo trình, phụ đề video) và luyện tập cả 4 kỹ năng xoay quanh nội dung đó, đồng thời được AI theo dõi lỗ hổng kiến thức của riêng mình theo thời gian.

Tuy nhiên, trong quá trình học tập tại trường, sinh viên thường chỉ tiếp cận các kỹ thuật này ở mức lý thuyết riêng lẻ (một bài tập RAG, một bài tập fine-tune...), chưa có cơ hội tích hợp chúng thành một sản phẩm hoàn chỉnh, có luồng nghiệp vụ thực tế. Xuất phát từ thực tế đó, nhóm lựa chọn đề tài này nhằm:

- Ứng dụng các kỹ thuật AI hiện đại (LLM, RAG, STT/TTS) vào một bài toán giáo dục cụ thể, có thể đo lường được.
- Xây dựng một sản phẩm có luồng trải nghiệm xuyên suốt 4 kỹ năng ngôn ngữ trên cùng một nguồn tài liệu cá nhân hóa.
- Phù hợp với định hướng nghiên cứu và năng lực triển khai của sinh viên năm cuối.

## 5. Mục tiêu của đề tài

### 5.1 Mục tiêu tổng quát

Nghiên cứu, thiết kế và xây dựng một nền tảng học tiếng Anh ứng dụng AI, cho phép người học cá nhân hóa nội dung học tập từ tài liệu của riêng mình, luyện tập đồng thời 4 kỹ năng Nghe – Nói – Đọc – Viết, và được hệ thống tự động theo dõi, thích ứng theo lỗ hổng kiến thức cá nhân.

### 5.2 Mục tiêu cụ thể

- Xây dựng hệ thống tiếp nhận đầu vào đa phương thức (văn bản, giọng nói) và không gian tri thức cá nhân (Notebook) dựa trên RAG.
- Xây dựng nhóm tính năng Đọc & Từ vựng: chế độ đọc lướt/quét thông tin có giới hạn thời gian (Skim & Scan Challenge), chế độ đọc cổ điển có trích dẫn nguồn theo đúng vị trí trong tài liệu (Classic Mode), tra từ tương tác, đoán nghĩa theo ngữ cảnh, sổ từ vựng với thuật toán lặp lại ngắt quãng (Spaced Repetition – SM-2), sinh truyện ngắn theo yêu cầu để ôn từ vựng (AI Custom Story).
- Xây dựng nhóm tính năng Nghe: tạo podcast tự động từ tài liệu, transcript tương tác đồng bộ theo từ, bài tập chép chính tả có chấm lỗi tự động.
- Xây dựng nhóm tính năng Viết: viết tóm tắt có chấm điểm (Summary Essay), chấm và sửa lỗi ngữ pháp trực tiếp trong văn bản (kiểu inline correction), gợi ý nâng cấp hành văn theo chuẩn CEFR/IELTS.
- Xây dựng nhóm tính năng Nói: "Bạn đồng hành hội thoại AI" (AI Conversation Partner) — người học nói theo lượt (turn-based) trong các tình huống mô phỏng thực tế, hệ thống chấm điểm đồng thời trên ba khía cạnh: độ chính xác phát âm (kế thừa từ Shadowing), mức độ phù hợp về ý định giao tiếp và sự lịch sự (kế thừa từ Roleplay), và phản hồi hội thoại tiếp theo bằng giọng nói.
- Xây dựng engine mô phỏng giọng nói vùng miền (regional accent simulation), cho phép người học tiếp cận tiếng Anh theo accent và từ lóng đặc trưng của từng khu vực.
- Xây dựng cơ chế học tập thích ứng và duy trì động lực học: nhật ký lỗi sai, thuật toán ưu tiên ôn tập dựa trên tần suất và độ mới của lỗi, sinh đề kiểm tra động theo điểm yếu cá nhân, cơ chế điểm danh chuỗi ngày học (Daily Streak).
- Xây dựng chức năng liên kết ngữ cảnh video thực tế (Movie Delivery Context): tìm kiếm và định vị chính xác thời điểm xuất hiện của một cụm từ/câu trong kho video có phụ đề.

## 6. Các tiêu chí đánh giá hệ thống

Nhóm tiến hành đánh giá hệ thống dựa trên các tiêu chí sau:

- Độ chính xác của các module chấm điểm AI (ngữ pháp, phát âm, hiểu ngữ cảnh) so với đánh giá của con người trên một tập mẫu thử nghiệm.
- Độ trễ phản hồi của các luồng tương tác thời gian thực (ghi âm → chấm điểm → phản hồi).
- Mức độ chính xác của việc truy xuất ngữ nghĩa (RAG) khi trả lời câu hỏi dựa trên tài liệu người dùng tải lên.
- Khả năng mở rộng thêm accent/vùng miền mới mà không cần huấn luyện lại mô hình.
- Trải nghiệm người dùng: mức độ mượt mà của luồng chuyển đổi giữa các kỹ năng trên cùng một tài liệu.

## 7. Cách tiếp cận và phương pháp thực hiện

### 7.1 Kiến trúc tổng quan

Hệ thống gồm: Frontend Web App (Next.js/React), Backend API (Python/FastAPI + LangChain), cơ sở dữ liệu quan hệ kết hợp vector store (PostgreSQL + pgvector), và tầng tích hợp các dịch vụ AI chuyên dụng (LLM, STT, TTS) thông qua API.

Riêng luồng "Bạn đồng hành hội thoại AI" (AI Conversation Partner) hoạt động theo mô hình **turn-based** — xử lý theo từng lượt nói, không streaming âm thanh hai chiều liên tục: người dùng ghi âm một lượt nói → hệ thống chuyển giọng nói thành văn bản (Whisper) → xử lý song song hai nhánh: (1) LLM sinh câu trả lời hội thoại tiếp theo, đồng thời đánh giá ý định giao tiếp và mức độ lịch sự; (2) dịch vụ đánh giá phát âm (Azure Pronunciation Assessment) chấm điểm độ chính xác âm vị trên chính đoạn ghi âm đó → kết quả tổng hợp được hiển thị dạng phản hồi và đọc lại bằng TTS để tiếp tục hội thoại. Cách tiếp cận turn-based giúp tránh các thách thức kỹ thuật của mô hình voice-to-voice thời gian thực liên tục (độ trễ thấp, xử lý ngắt lời, streaming hai chiều), phù hợp hơn với thời gian và nguồn lực của một khóa luận, trong khi vẫn giữ được trải nghiệm "giao tiếp với AI và được chỉnh phát âm ngay" là điểm nhấn chính của tính năng.

### 7.2 Phân nhóm chức năng theo mức độ ưu tiên

Do phạm vi tính năng ban đầu tương đối rộng, nhóm phân loại các chức năng thành ba mức để đảm bảo tính khả thi trong thời gian thực hiện khóa luận:

**Mức 1 – Triển khai đầy đủ (MVP):**
Tiếp nhận đầu vào đa phương thức; Notebook cá nhân hóa (RAG); Skim & Scan Challenge; Classic Mode (trích dẫn nguồn theo vị trí); tra từ tương tác; đoán nghĩa theo ngữ cảnh; sổ từ vựng SM-2; AI Custom Story; podcast/transcript tương tác; chép chính tả (Dictation); Summary Essay; chấm lỗi ngữ pháp inline; gợi ý nâng cấp hành văn (AI Rephrase); nhật ký lỗi và thuật toán ưu tiên ôn tập; sinh đề kiểm tra động; Daily Streak.

**Mức 2 – Triển khai ở dạng thử nghiệm giới hạn:**
Bạn đồng hành hội thoại AI (turn-based, hợp nhất chấm phát âm kiểu Shadowing và chấm ý định/lịch sự kiểu Roleplay trong cùng một luồng); engine mô phỏng accent vùng miền (giới hạn 2 accent để đánh giá tính khả thi và độ chính xác, ví dụ Southern US và British).

**Mức 3 – Định hướng mở rộng (đề xuất, chưa triển khai đầy đủ):**
Nâng cấp Bạn đồng hành hội thoại AI lên chế độ voice-to-voice thời gian thực liên tục (streaming, xử lý ngắt lời); Movie Delivery Context (liên kết ngữ cảnh video thực tế quy mô lớn); mở rộng thêm nhiều accent vùng miền khác.

## 8. Phạm vi nghiên cứu

- Nền tảng học tiếng Anh ở quy mô cá nhân hóa cho từng người dùng, không nhắm đến quy mô hạ tầng lớp (large-scale) trong giai đoạn khóa luận.
- Giọng nói sử dụng trong hệ thống (chatbot, podcast, Bạn đồng hành hội thoại AI) được lấy từ thư viện giọng có bản quyền/được cấp phép hợp lệ của nhà cung cấp TTS (ví dụ giọng cộng đồng đã đăng ký trên ElevenLabs), gắn với các persona nguyên bản do nhóm xây dựng — **không thực hiện nhân bản (clone) giọng nói của người nổi tiếng hoặc bất kỳ cá nhân có thật nào khi chưa có sự đồng ý của họ**, nhằm đảm bảo tuân thủ điều khoản dịch vụ và tránh rủi ro về quyền hình ảnh/giọng nói cá nhân.
- Mô phỏng accent vùng miền giới hạn ở 1–2 khu vực tiêu biểu để tập trung đánh giá tính khả thi và chất lượng, thay vì dàn trải nhiều vùng.
- Không triển khai các chức năng nâng cao như: thanh toán, hạ tầng video streaming thời gian thực quy mô lớn, chế độ voice-to-voice thời gian thực liên tục cho tính năng hội thoại AI (các mục này được đưa vào định hướng mở rộng ở mục 7.2).

## 9. Đánh giá khả năng thực hiện của nhóm

Nhóm đánh giá đề tài ở mức khó, do liên quan đến việc tích hợp nhiều công nghệ AI khác nhau (LLM, RAG, STT, TTS) trong cùng một hệ thống. Tuy nhiên, phạm vi đã được kiểm soát thông qua việc phân loại chức năng theo ba mức ưu tiên (mục 7.2), giúp đảm bảo có một sản phẩm lõi (MVP) hoàn chỉnh, có thể đánh giá được, trong khi các chức năng phức tạp hơn được thử nghiệm ở quy mô giới hạn hoặc trình bày như định hướng phát triển — phù hợp với năng lực và thời gian thực hiện của sinh viên năm cuối.