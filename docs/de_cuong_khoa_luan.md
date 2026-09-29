# Đề cương khóa luận tốt nghiệp

## 1. Tên đề tài

**Đề xuất (khuyến nghị chọn):**
> Lumina — Nghiên cứu và xây dựng nền tảng học tiếng Anh cá nhân hóa xuyên suốt bốn kỹ năng Nghe – Nói – Đọc – Viết dựa trên tài liệu người dùng, ứng dụng mô hình ngôn ngữ lớn (LLM) và truy xuất tăng cường ngữ nghĩa (RAG)

**Các phương án khác:**
1. Nghiên cứu và xây dựng nền tảng học tiếng Anh cá nhân hóa tích hợp bốn kỹ năng ứng dụng mô hình ngôn ngữ lớn và truy xuất tăng cường (RAG)
2. Xây dựng hệ thống học tiếng Anh thích ứng đa kỹ năng dựa trên tài liệu cá nhân hóa và mô hình ngôn ngữ lớn
3. Nghiên cứu và phát triển nền tảng học tiếng Anh ứng dụng AI: cá nhân hóa lộ trình học và mô phỏng giao tiếp thực tế trên tài liệu người dùng

*Lý do khuyến nghị phương án chính: nêu được cả ba trụ cột của đề tài — (1) tính mới: cá nhân hóa xuyên suốt 4 kỹ năng trên cùng nguồn tài liệu, (2) công nghệ: LLM + RAG, (3) đóng góp: hệ thống có tên sản phẩm cụ thể (Lumina), thể hiện tính hoàn chỉnh của sản phẩm chứ không chỉ là nghiên cứu lý thuyết.*

## 2. Lý do chọn đề tài

Hiện nay, các ứng dụng học tiếng Anh phổ biến (Duolingo, ELSA Speak, Cambly...) thường tập trung vào một kỹ năng riêng lẻ (từ vựng, phát âm, hội thoại), thiếu sự liên kết xuyên suốt giữa các kỹ năng Nghe – Nói – Đọc – Viết trên cùng một nguồn tài liệu học tập của người dùng. Bên cạnh đó, phần lớn các ứng dụng chấm điểm dựa trên quy tắc cố định (rule-based), chưa tận dụng được khả năng hiểu ngữ cảnh và cá nhân hóa sâu mà các mô hình ngôn ngữ lớn (LLM) hiện đại có thể mang lại.

Sự phát triển của các công nghệ AI trong vài năm gần đây — mô hình ngôn ngữ lớn (LLM), nhận diện giọng nói (Whisper, Azure Speech), tổng hợp giọng nói (Text-to-Speech), và cơ sở dữ liệu vector phục vụ truy xuất ngữ nghĩa (RAG) — đã tạo điều kiện kỹ thuật để xây dựng một nền tảng học tập cá nhân hóa sâu hơn: người học có thể tải lên chính tài liệu họ quan tâm (bản ghi âm, tài liệu .docx) và luyện tập cả 4 kỹ năng xoay quanh nội dung đó, đồng thời được AI theo dõi lỗ hổng kiến thức và thói quen học tập của riêng mình theo thời gian.

Tuy nhiên, trong quá trình học tập tại trường, sinh viên thường chỉ tiếp cận các kỹ thuật này ở mức lý thuyết riêng lẻ (một bài tập RAG, một bài tập fine-tune...), chưa có cơ hội tích hợp chúng thành một sản phẩm hoàn chỉnh, có luồng nghiệp vụ thực tế. Xuất phát từ thực tế đó, nhóm lựa chọn đề tài này nhằm:

- Ứng dụng các kỹ thuật AI hiện đại (LLM, RAG, STT/TTS) vào một bài toán giáo dục cụ thể, có thể đo lường được.
- Xây dựng một sản phẩm có luồng trải nghiệm xuyên suốt 4 kỹ năng ngôn ngữ trên cùng một nguồn tài liệu cá nhân hóa.
- Phù hợp với định hướng nghiên cứu và năng lực triển khai của sinh viên năm cuối.

## 3. Mục tiêu của đề tài

### 3.1 Mục tiêu tổng quát

Nghiên cứu, thiết kế và xây dựng một nền tảng học tiếng Anh ứng dụng AI, cho phép người học cá nhân hóa nội dung học tập từ tài liệu của riêng mình, luyện tập đồng thời 4 kỹ năng Nghe – Nói – Đọc – Viết, và được hệ thống tự động theo dõi, thích ứng theo lỗ hổng kiến thức và thói quen học tập cá nhân.

### 3.2 Mục tiêu cụ thể

- Xây dựng hệ thống tiếp nhận đầu vào giới hạn ở **âm thanh (audio)** và **văn bản .docx** (không xử lý đa phương thức mở rộng như ảnh, PDF, video), và không gian tri thức cá nhân (Notebook) dựa trên RAG.
- Xây dựng nhóm tính năng Đọc & Từ vựng: chế độ đọc lướt/quét thông tin có giới hạn thời gian (Skim & Scan Challenge), chế độ đọc cổ điển có trích dẫn nguồn theo đúng vị trí trong tài liệu (Classic Mode), tra từ tương tác, đoán nghĩa theo ngữ cảnh, sổ từ vựng với thuật toán lặp lại ngắt quãng (Spaced Repetition – SM-2), sinh truyện ngắn theo yêu cầu để ôn từ vựng (AI Custom Story).
- Xây dựng nhóm tính năng Nghe: tạo podcast tự động từ tài liệu, transcript tương tác đồng bộ theo từ, bài tập chép chính tả có chấm lỗi tự động.
- Xây dựng nhóm tính năng Viết: viết luận có chấm điểm với 3 nguồn đề bài — tóm tắt tài liệu đã học (Summary), chủ đề mở rộng liên quan đến tài liệu (Extended Topic), và chủ đề tự chọn kèm gợi ý đề theo phong cách chứng chỉ quốc tế TOEIC/IELTS/Cambridge (Free Topic); chấm và sửa lỗi ngữ pháp trực tiếp trong văn bản (inline correction); gợi ý nâng cấp hành văn theo chuẩn CEFR/IELTS.
- Xây dựng "Bạn đồng hành hội thoại AI" (AI Conversation Partner) — người học nói theo lượt (turn-based) trong các tình huống mô phỏng thực tế, hệ thống chấm điểm đồng thời trên ba khía cạnh: độ chính xác phát âm, mức độ phù hợp về ý định giao tiếp và sự lịch sự, và phản hồi hội thoại tiếp theo bằng giọng nói. Tích hợp trực tiếp trong luồng hội thoại này các cụm từ giao tiếp hàng ngày (daily speaking) và slang cơ bản theo ngữ cảnh, có nguồn tham chiếu rõ ràng, kèm **Sổ tay Slang/Cụm thoại** để người học xem lại và ôn tập.
- Xây dựng **Adaptive Learning Engine**: nhật ký lỗi sai, thuật toán ưu tiên ôn tập dựa trên tần suất và độ mới của lỗi, sinh đề kiểm tra động theo điểm yếu cá nhân, theo dõi và mô hình hóa thói quen học tập (tần suất học, khung giờ, kỹ năng được ưu tiên, tốc độ tiến bộ) để hệ thống ngày càng hiểu người học hơn theo thời gian, cơ chế điểm danh chuỗi ngày học (Daily Streak).
- Xây dựng chức năng liên kết ngữ cảnh video thực tế (Movie Delivery Context): tìm kiếm và định vị chính xác thời điểm xuất hiện của một cụm từ/câu trong kho video có phụ đề.

## 4. Các tiêu chí đánh giá hệ thống

Nhóm tiến hành đánh giá hệ thống dựa trên các tiêu chí sau:

- Độ chính xác của các module chấm điểm AI (ngữ pháp, phát âm, hiểu ngữ cảnh) so với đánh giá của con người trên một tập mẫu thử nghiệm.
- Độ trễ phản hồi của các luồng tương tác thời gian thực (ghi âm → chấm điểm → phản hồi).
- Mức độ chính xác của việc truy xuất ngữ nghĩa (RAG) khi trả lời câu hỏi dựa trên tài liệu người dùng tải lên.
- Mức độ hữu ích của Adaptive Learning Engine trong việc cá nhân hóa nội dung ôn tập theo thời gian sử dụng.
- Trải nghiệm người dùng: mức độ mượt mà của luồng chuyển đổi giữa các kỹ năng trên cùng một tài liệu.

## 5. Cách tiếp cận và phương pháp thực hiện

### 5.1 Kiến trúc tổng quan

Hệ thống gồm: Frontend Web App (Next.js/React), Backend API (Python/FastAPI + LangChain), cơ sở dữ liệu quan hệ kết hợp vector store (PostgreSQL + pgvector), và tầng tích hợp các dịch vụ AI chuyên dụng (LLM, STT, TTS) thông qua API.

Riêng luồng "Bạn đồng hành hội thoại AI" hoạt động theo mô hình turn-based — xử lý theo từng lượt nói, không streaming âm thanh hai chiều liên tục: người dùng ghi âm một lượt nói → hệ thống chuyển giọng nói thành văn bản qua Azure Speech-to-Text (ưu tiên; nếu lỗi/timeout, tự động fallback sang Whisper để đảm bảo tính sẵn sàng — xem mục 9.4) → xử lý song song hai nhánh: (1) LLM sinh câu trả lời hội thoại tiếp theo, đồng thời đánh giá ý định giao tiếp, mức độ lịch sự, và gợi ý cụm từ/slang phù hợp ngữ cảnh; (2) dịch vụ đánh giá phát âm (Azure Pronunciation Assessment — không có fallback, vì đây là khả năng chuyên biệt chỉ Azure có) chấm điểm độ chính xác âm vị trên chính đoạn ghi âm đó → kết quả tổng hợp được hiển thị dạng phản hồi và đọc lại bằng TTS để tiếp tục hội thoại. Cách tiếp cận turn-based giúp tránh các thách thức kỹ thuật của mô hình voice-to-voice thời gian thực liên tục, phù hợp hơn với thời gian và nguồn lực của một khóa luận.

### 5.2 Phân nhóm chức năng theo module kỹ năng

Hệ thống được phân chia thành các **module theo kỹ năng/chức năng**, mỗi tính năng con được gắn nhãn mức độ triển khai để đảm bảo tính khả thi trong thời gian thực hiện khóa luận:
**(Đầy đủ)** — triển khai hoàn chỉnh; **(Thử nghiệm giới hạn)** — triển khai quy mô nhỏ để kiểm chứng tính khả thi; **(Định hướng mở rộng)** — đề xuất, chưa triển khai trong phạm vi khóa luận.

**Module 0 — Lõi hệ thống & Cá nhân hóa**
- Tiếp nhận đầu vào (audio, văn bản .docx) và Notebook cá nhân hóa dựa trên RAG *(Đầy đủ)*
- Adaptive Learning Engine: nhật ký lỗi, hàng đợi ưu tiên ôn tập, sinh đề kiểm tra động, theo dõi thói quen học tập theo thời gian *(Đầy đủ)*
- Daily Streak *(Đầy đủ)*

**Module 1 — Đọc & Từ vựng (Reading)**
- Skim & Scan Challenge *(Đầy đủ)*
- Classic Mode — trích dẫn nguồn theo vị trí *(Đầy đủ)*
- Tra từ tương tác, đoán nghĩa theo ngữ cảnh *(Đầy đủ)*
- Sổ từ vựng SM-2 *(Đầy đủ)*
- AI Custom Story *(Đầy đủ)*
- Rearrange the Block — nhánh Reading *(Thử nghiệm giới hạn)*

**Module 2 — Nghe (Listening)**
- Podcast tự động từ tài liệu *(Đầy đủ)*
- Transcript tương tác đồng bộ từ *(Đầy đủ)*
- Dictation — chấm lỗi tự động *(Đầy đủ)*

**Module 3 — Viết (Writing)**
- Viết luận — 3 nguồn đề bài: Tóm tắt tài liệu (Summary), Chủ đề mở rộng liên quan tài liệu (Extended Topic), Chủ đề tự chọn kèm gợi ý theo phong cách chứng chỉ TOEIC/IELTS/Cambridge (Free Topic) *(Đầy đủ)*
- Inline Grammar Correction *(Đầy đủ)*
- AI Rephrase — nâng cấp hành văn CEFR/IELTS *(Đầy đủ)*
- Rearrange the Block — nhánh Writing/Grammar *(Thử nghiệm giới hạn)*

*Ghi chú: "Viết luận" thay thế tên gọi "Summary Essay" trước đây — Summary vẫn là 1 trong 3 nguồn đề (chấm theo coverage ý chính so với tài liệu), trong khi Extended Topic và Free Topic dùng chung 1 rubric 4 tiêu chí (Task Response, Coherence & Cohesion, Lexical Resource, Grammatical Range & Accuracy) để tránh phát sinh 3 hệ thống chấm riêng theo từng chứng chỉ — phong cách chứng chỉ (TOEIC/IELTS/Cambridge) chỉ ảnh hưởng đến cách sinh đề bài, không ảnh hưởng đến cách chấm điểm. Chi tiết flow, business rules, và endpoint xem tài liệu kỹ thuật `docs/feature-writing.md`, `docs/api-spec.md`.*

**Module 4 — Nói (Speaking)**
- Bạn đồng hành hội thoại AI (turn-based; chấm phát âm + ý định/lịch sự) *(Thử nghiệm giới hạn)*
- Daily Speaking & Slang cơ bản — tích hợp trong luồng hội thoại, kèm Sổ tay Slang/Cụm thoại để lưu và ôn tập *(Thử nghiệm giới hạn)*
- Nâng cấp lên voice-to-voice thời gian thực liên tục *(Định hướng mở rộng)*

**Module 5 — Mở rộng nền tảng**
- Browser Extension: tra từ trên web *(Thử nghiệm giới hạn)*, tra từ trong phụ đề YouTube *(Định hướng mở rộng)*
- Movie Delivery Context — nhánh đọc mẫu bằng TTS (`movie_context_tts_fallback`) *(Thử nghiệm giới hạn)*
- Movie Delivery Context — nhánh tìm video thật (`video_sources`/`video_subtitle_index`) *(Định hướng mở rộng)*

*Ghi chú: Movie Delivery Context tách thành 2 nhánh tier khác nhau (khác với bản mô tả trước đây coi là 1 khối). Nhánh TTS fallback có độ khó triển khai thấp — tái sử dụng hoàn toàn `llm_service` (sinh câu ví dụ) và `speech_service` TTS (đã bắt buộc xây cho Module 2/4), không phát sinh logic/tích hợp mới — nên đủ điều kiện Thử nghiệm giới hạn. Nhánh tìm video thật vẫn ở Định hướng mở rộng vì cần thu thập/index kho video có phụ đề, phức tạp hơn nhiều và chưa khả thi trong phạm vi khóa luận hiện tại. Cần lưu ý khi trình bày: nếu chỉ triển khai nhánh TTS fallback mà chưa có nhánh video thật, giá trị khác biệt của tính năng so với các chức năng sinh câu ví dụ + TTS đã có ở module khác (Vocab lookup, Podcast) là hạn chế — nên định vị rõ đây là bước đệm hạ tầng cho nhánh video thật sau này, không phải sản phẩm hoàn chỉnh.

Cách phân nhóm này trình bày rõ phạm vi triển khai theo từng kỹ năng ngôn ngữ — phù hợp với cấu trúc đánh giá 4 kỹ năng của khóa luận — trong khi vẫn giữ nguyên tắc kiểm soát phạm vi thông qua nhãn mức độ triển khai gắn trên từng tính năng.

## 6. Phạm vi nghiên cứu

- Nền tảng học tiếng Anh ở quy mô cá nhân hóa cho từng người dùng, không nhắm đến quy mô hạ tầng lớn (large-scale) trong giai đoạn khóa luận.
- Giọng nói sử dụng trong hệ thống (chatbot, podcast, Bạn đồng hành hội thoại AI) được lấy từ thư viện giọng có bản quyền/được cấp phép hợp lệ của nhà cung cấp TTS, gắn với các persona nguyên bản do nhóm xây dựng — không thực hiện nhân bản (clone) giọng nói của người nổi tiếng hoặc bất kỳ cá nhân có thật nào.
- Không thực hiện mô phỏng accent vùng miền theo giọng bản địa từng khu vực; thay vào đó, tập trung vào các cụm từ giao tiếp hàng ngày (daily speaking) và slang cơ bản có nguồn tham chiếu, tích hợp trực tiếp trong luồng Bạn đồng hành hội thoại AI.
- Đầu vào tài liệu học tập giới hạn ở hai định dạng: âm thanh (audio) và văn bản .docx, áp dụng cho toàn bộ các điểm tải tài liệu trong hệ thống.
- Không triển khai các chức năng nâng cao như: thanh toán, hạ tầng video streaming thời gian thực quy mô lớn, chế độ voice-to-voice thời gian thực liên tục cho tính năng hội thoại AI (các mục này được đưa vào định hướng mở rộng ở mục 5.2).

## 7. Đánh giá khả năng thực hiện của nhóm

Nhóm đánh giá đề tài ở mức khó, do liên quan đến việc tích hợp nhiều công nghệ AI khác nhau (LLM, RAG, STT, TTS) trong cùng một hệ thống. Tuy nhiên, phạm vi đã được kiểm soát thông qua việc phân loại chức năng theo module kỹ năng kèm nhãn mức độ triển khai (mục 5.2), giúp đảm bảo có một sản phẩm lõi hoàn chỉnh, có thể đánh giá được, trong khi các chức năng phức tạp hơn được thử nghiệm ở quy mô giới hạn hoặc trình bày như định hướng phát triển — phù hợp với năng lực và thời gian thực hiện của sinh viên năm cuối.

## 8. Lộ trình triển khai (đề xuất, ưu tiên theo phụ thuộc kỹ thuật)

| Giai đoạn | Thời lượng ước tính | Nội dung | Lý do ưu tiên |
|---|---|---|---|
| 1 | Tuần 1–3 | Hạ tầng lõi: DB schema, auth, Notebook ingestion (audio + docx), pipeline RAG | Nền tảng bắt buộc cho mọi module khác |
| 2 | Tuần 4–6 | Module Đọc & Từ vựng | Tái sử dụng trực tiếp RAG, ít phụ thuộc dịch vụ ngoài, rủi ro kỹ thuật thấp nhất |
| 3 | Tuần 7–9 | Module Viết | Tạo nguồn dữ liệu lỗi (grammar errors) làm đầu vào cho Adaptive Learning Engine |
| 4 | Tuần 10–11 | Module Nghe | Độ phức tạp trung bình, không phụ thuộc các module trước |
| 5 | Tuần 12–13 | Adaptive Learning Engine (mở rộng) + Daily Streak | Cần dữ liệu lỗi/tương tác tích lũy từ 3 module trên để có ý nghĩa |
| 6 | Tuần 14–16 | Module Nói: Bạn đồng hành hội thoại AI + Daily Speaking & Slang | Phức tạp nhất — tích hợp song song Azure Speech + LLM, nên triển khai sau khi các luồng cơ bản đã ổn định |
| 7 | Tuần 17–18 | Rearrange the Block (Reading/Writing) | Phụ thuộc trực tiếp vào Adaptive Learning Engine (error tracking) đã ổn định ở giai đoạn 5 |
| 8 | Tuần 19–20 (nếu còn thời gian) | Browser Extension (web lookup → YouTube subtitle) | Độc lập với các module còn lại, có thể lược bỏ hoặc rút gọn nếu thiếu thời gian |

*Movie Delivery Context — nhánh TTS fallback (`movie_context_tts_fallback`): gộp vào cuối Giai đoạn 8 (tuần 19-20), sau khi `speech_service` TTS đã sẵn sàng từ Giai đoạn 4. Chi phí triển khai thấp (tái sử dụng hoàn toàn `llm_service` + `speech_service`, không logic mới) nên không cần riêng 1 giai đoạn. Nhánh tìm video thật (`video_sources`/`video_subtitle_index`) không nằm trong lộ trình 20 tuần — giữ nguyên vai trò định hướng mở rộng (mục 5.2).*

## 9. Kiến trúc hệ thống chi tiết

### 9.1. Nguyên tắc phân lớp

Hệ thống được tổ chức theo 3 lớp rõ ràng:

- `router`: nhận request, validate bằng Pydantic schema, gọi service và trả response.
- `feature_service`: điều phối nghiệp vụ theo miền chức năng như reading, writing, speaking, vocab.
- `infra_service` và model: làm việc trực tiếp với LLM, Speech, RAG và PostgreSQL thông qua SQLAlchemy ORM.

Nguyên tắc vận hành là router không gọi thẳng `llm_service` hoặc `speech_service`, mà luôn đi qua service nghiệp vụ tương ứng. Extension trình duyệt tuân theo nguyên tắc tương tự ở phía client: không gọi trực tiếp API nội bộ của Gemini/Azure, chỉ gọi qua các endpoint REST đã có sẵn của backend (tái sử dụng nguyên `vocab_service`/`llm_service`, không tạo luồng xử lý song song riêng).

### 9.2. Các quyết định triển khai chính

- `llm_service.py` là lớp bọc duy nhất cho Gemini thông qua `langchain-google-genai`, giúp đổi provider sau này ít tác động đến feature service.
- `speech_service.py` là điểm gom cho STT, TTS và chấm phát âm; khởi tạo `SpeechConfig` một lần rồi tái sử dụng.
- Audio đầu vào phải được chuẩn hóa về PCM WAV 16 kHz mono trước khi đưa vào Azure Speech SDK.
- Database dùng SQLAlchemy 2.0 async ORM cho backend, kết hợp Alembic cho migration.
- `core/config.py` đọc `.env` qua một điểm duy nhất và tách `DATABASE_URL` async với `DATABASE_URL_SYNC` cho Alembic.
- Test ưu tiên DB thật trong môi trường test riêng, chỉ mock ở các boundary thực sự tốn phí hoặc phụ thuộc mạng.
- Extension được xây trên chuẩn Manifest V3, không dùng background page thường trực (đã bị loại bỏ ở V3) mà dùng service worker theo sự kiện, phù hợp giới hạn vòng đời của nền tảng extension hiện đại.

### 9.3. Hai luồng RAG riêng biệt

- **Classic Mode**: tài liệu người dùng upload (audio hoặc .docx) được chunk, embed và truy xuất top-k từ pgvector; phản hồi phải có trích dẫn đúng theo chunk gốc.
- **Skim & Scan**: Gemini sinh đoạn văn mới theo chủ đề/trình độ, sau đó hệ thống tự chunk lại để tạo self-citation; luồng này không phụ thuộc tài liệu Notebook.

Hai luồng này không dùng chung một hàm, vì bản chất bài toán khác nhau: một bên là grounding trên nguồn có thật, một bên là sinh nội dung mới để luyện tập.

### 9.4. Luồng hội thoại AI và Daily Speaking & Slang

Bạn đồng hành hội thoại AI được chốt theo mô hình **turn-based**. Mỗi lượt nói đi qua chuỗi xử lý: ghi âm → STT → chấm phát âm → LLM sinh phản hồi, đánh giá ý định/lịch sự, đồng thời gợi ý cụm từ/slang phù hợp ngữ cảnh lượt hội thoại đó → TTS đọc lại phản hồi.

**STT dùng 2 provider theo mô hình ưu tiên/dự phòng**: Azure Speech-to-Text là lựa chọn ưu tiên; nếu lỗi/timeout (đã retry 1 lần), hệ thống tự động fallback sang Whisper (OpenAI Whisper API) để đảm bảo tính sẵn sàng của luồng hội thoại. Đây **chỉ** áp dụng cho STT thuần (lấy transcript đưa vào LLM) — **không** áp dụng cho Azure Pronunciation Assessment (chấm điểm âm vị), vì đây là khả năng chuyên biệt không có provider nào khác thay thế được; nếu Azure Pronunciation Assessment lỗi, hệ thống trả về điểm phát âm NULL kèm cờ lỗi thay vì cố tìm provider thay thế. Việc phân biệt rõ 2 nhánh này (nhánh nào có fallback, nhánh nào không) là điểm quan trọng cần trình bày đúng khi bảo vệ khóa luận, tránh gây hiểu lầm rằng toàn bộ luồng STT/chấm điểm đều có thể thay thế bằng Whisper.

Gợi ý slang/cụm thoại được sinh **cùng một lệnh gọi LLM** với phần đánh giá ý định/lịch sự (không tách thành lệnh gọi riêng), kèm nguồn tham chiếu rõ ràng để đảm bảo tính chính xác. Người học có thể lưu cụm từ gợi ý vào **Sổ tay Slang/Cụm thoại** cá nhân để xem lại sau (chi tiết schema xem mục 10.1).

Mô hình turn-based là nền tảng hiện tại; chế độ voice-to-voice thời gian thực liên tục chỉ là định hướng mở rộng (Module 4).

### 9.5. Kiến trúc Browser Extension và xác thực dùng chung phiên đăng nhập

**Cấu trúc extension (Manifest V3):**

```
extension/
├── manifest.json
├── background.js        # service worker — quản lý token, gọi API backend
├── content-script.js    # inject vào mọi trang, bắt sự kiện bôi đen/double-click
├── content-script-yt.js # (Định hướng mở rộng) chạy riêng trên youtube.com, đọc caption
├── popup/                # UI khi click icon extension
└── lookup-overlay.js     # component hiển thị popup nghĩa từ, dạng inject
```

Content script không được phép gọi thẳng API cross-origin của backend; mọi request phải chuyển qua background service worker (có khai báo `host_permissions`), giữ đúng ranh giới bảo mật của Manifest V3.

**Xác thực — cơ chế "linking cookie" (thiết kế ban đầu; TRONG TRIỂN KHAI ĐÃ THAY bằng đăng nhập ở popup extension + `client_type` từ 2026-09-26 — cookie đọc được làm tăng bề mặt tấn công mà không thêm quyền gì, xem `lumina_context.md` mục 3.14):** vì `security.py` hiện phát JWT qua `OAuth2PasswordBearer` (header `Authorization: Bearer`), extension không thể đọc trực tiếp phiên đăng nhập của web app. Giải pháp áp dụng, tương tự cách Notion Web Clipper/Grammarly liên kết extension với tài khoản web:

1. Khi đăng nhập trên web app, backend set thêm một cookie ngắn hạn (TTL ~5 phút), scope theo domain chính, chứa một mã liên kết (`link_code`) chứ không phải access token thật.
2. Extension đọc cookie này qua `chrome.cookies` API, gửi `link_code` tới endpoint mới `POST /api/auth/extension-token` để đổi lấy cặp access/refresh token riêng cho extension.
3. Refresh token của extension được lưu trong bảng `refresh_tokens` đã có sẵn — chỉ cần thêm một cột phân biệt nguồn phát hành, tận dụng nguyên cơ chế revoke đã thiết kế từ đầu (mục 10.3).

Cách này đảm bảo: (a) người dùng không phải đăng nhập lại lần hai trên extension, (b) logout ở một client không ảnh hưởng client còn lại vì mỗi client giữ refresh token độc lập, (c) không cần thay đổi cơ chế JWT hiện có của web app.

### 9.6. Kiến trúc Adaptive Learning Engine và Rearrange the Block

Adaptive Learning Engine (Module 0, Đầy đủ) và bài tập Rearrange the Block (Module 1/3, Thử nghiệm giới hạn) dùng chung một subsystem lõi, `error_tracking_service.py`, đóng vai trò nguồn dữ liệu chung cho cả việc sinh bài tập lẫn thuật toán ưu tiên ôn tập:

- **Nguồn nội dung cho Rearrange the Block**: ưu tiên tái sử dụng lỗi sai đã ghi nhận của chính người học (từ `user_errors`); khi chưa đủ dữ liệu lỗi (người dùng mới, hoặc lỗi thuộc loại hiếm), fallback sang nội dung bài học có sẵn hoặc sinh mới qua Gemini.
- **Chấm điểm**: partial credit theo tỷ lệ vị trí khối đặt đúng trên tổng số khối, thay vì chấm nhị phân đúng/sai toàn bài.
- **Phân loại lỗi — cách tiếp cận hybrid theo dạng bài**:
  - Bài tập dạng đóng (closed-form, ví dụ điền từ/chọn đáp án): dùng rule-based diff giữa câu trả lời và đáp án chuẩn.
  - Bài tập dạng mở (open-ended, ví dụ Writing tự luận): tận dụng (piggyback) Gemini structured output ngay trên các lệnh gọi đánh giá Writing đã có sẵn, tránh phát sinh thêm lệnh gọi LLM riêng.
- **Thay thế schema cũ**: bảng `error_log` tổng hợp chung trước đây được thay bằng hai bảng chuyên biệt hơn, `quiz_attempts` và `user_errors` (chi tiết mục 10.1), phản ánh đúng nhu cầu lưu vết từng lượt làm bài và từng lỗi riêng lẻ có gắn nhãn phân loại.

Vì Adaptive Learning Engine ở tier Đầy đủ (MVP), hai bảng `quiz_attempts` và `user_errors` là hạ tầng lõi cần có ngay từ giai đoạn đầu (mục 8, giai đoạn 3); riêng bài tập Rearrange the Block — vốn chỉ là một trong nhiều "người tiêu dùng" của hai bảng này — mới ở tier Thử nghiệm giới hạn.

### 9.7. Kiến trúc chọn đề bài Viết (Writing Prompt Selection)

Tính năng Viết luận (Module 3) hỗ trợ 3 nguồn đề bài thay vì chỉ tóm tắt tài liệu như bản mô tả ban đầu:

- **Tóm tắt tài liệu** (`document_summary`): giữ nguyên thiết kế gốc, chấm theo mức độ bao phủ ý chính (`document_chunks` làm ground truth).
- **Chủ đề mở rộng** (`extended_topic`): Gemini xác định chủ đề chính của tài liệu rồi sinh 1 đề luận ý kiến/thảo luận liên quan, không yêu cầu tóm tắt lại nội dung.
- **Chủ đề tự chọn** (`free_topic`): người học tự nhập đề, hoặc xin gợi ý đề theo phong cách chứng chỉ quốc tế (TOEIC/IELTS/Cambridge).

**Quyết định kiến trúc quan trọng**: `extended_topic` và `free_topic` dùng **chung 1 rubric chấm điểm** 4 tiêu chí (Task Response, Coherence & Cohesion, Lexical Resource, Grammatical Range & Accuracy — mượn cấu trúc phổ biến của IELTS Writing Task 2), thay vì xây riêng rubric cho từng chứng chỉ TOEIC/IELTS/Cambridge. Phong cách chứng chỉ chỉ ảnh hưởng đến **cách sinh đề bài** (độ dài, dạng câu hỏi, văn phong kỳ vọng), không ảnh hưởng đến **cách chấm điểm** — quyết định này giữ phạm vi triển khai trong tầm kiểm soát, tránh phát sinh 3 hệ thống chấm điểm riêng biệt đòi hỏi kiểm chứng độ chính xác với 3 chuẩn chấm khác nhau. Khi trình bày khóa luận, cần nêu rõ: hệ thống mô phỏng phong cách đề bài của các chứng chỉ, không cam kết độ chính xác chấm điểm tương đương giám khảo chứng chỉ thật.

Chi tiết flow, business rules, edge cases và endpoint xem `docs/feature-writing.md` mục 1 và `docs/api-spec.md` mục 5.

## 10. Thiết kế dữ liệu đã thống nhất

### 10.1. Các nhóm thực thể lõi

Schema được xây quanh các cụm dữ liệu dùng chung thay vì tách bảng riêng cho từng tính năng:

- `users`: danh tính người học và cấu hình cá nhân.
- `documents` + `document_chunks`: tài liệu upload (audio hoặc .docx) và dữ liệu RAG.
- `learning_attempt` theo nghĩa chung: mọi lượt học đều gắn với `user_id` và có thể gắn `document_id` nếu cần.
- `quiz_attempts` + `user_errors`: nơi tổng hợp lượt làm bài và lỗi xuyên suốt các kỹ năng, thay thế bảng `error_log` tổng quát trước đây; mỗi bản ghi `user_errors` gắn nhãn phân loại theo enum `error_type` cố định (giá trị enum cụ thể xem mục 11).
- `personas`: thư viện giọng nói hợp lệ (không có bảng `accents` — do đã loại bỏ mô phỏng accent vùng miền, xem mục 6).
- `slang_phrases`: thư viện cụm từ/slang tham chiếu, gắn nguồn (nguồn tham khảo, mức độ trang trọng) để LLM gợi ý đúng ngữ cảnh trong lượt hội thoại.
- `user_phrasebook_entries`: Sổ tay Slang/Cụm thoại cá nhân — bản ghi cụm từ người học đã lưu lại để ôn tập, tham chiếu tới `slang_phrases.id` (nullable, vì cụm từ có thể do LLM sinh tại chỗ, chưa nằm sẵn trong thư viện) và tới `conversation_turns.id` (nullable) để giữ ngữ cảnh hội thoại gốc.
- `review_priority_queue`: hàng đợi ưu tiên ôn tập tổng hợp từ từ vựng và lỗi.

### 10.2. Mức ưu tiên triển khai (đối chiếu tier ở mục 5.2)

- **Đầy đủ (MVP)**: `users`, `documents`, `notebook_folders`, `document_chunks`, `generated_passages`, `vocab_items`, `vocab_reviews`, `reading_sessions`, `reading_answers`, `contextual_guess_attempts`, `custom_stories`, `podcasts`, `transcript_segments`, `dictation_attempts`, `writing_submissions`, `writing_insights`, `rephrase_requests`, `review_priority_queue`, `quizzes`, `quiz_attempts`, `user_errors`, `streaks`, `skill_progress`, `personas`.
- **Thử nghiệm giới hạn**: `scenarios`, `conversation_sessions`, `conversation_turns`, `slang_phrases`, `user_phrasebook_entries`; bổ sung cho Extension: cột `client_type` trên `refresh_tokens` (phân biệt `'web'` | `'extension'`), cột `source_url` trên `vocab_items` (nullable, lưu URL trang ngoài khi từ được tra qua extension thay vì qua Notebook).
- **Định hướng mở rộng**: `realtime_conversation_metrics`, `movie_context_tts_fallback`, `movie_context_matches`, `video_sources`, `video_subtitle_index`.

*Lưu ý: `quiz_attempts` và `user_errors` được nâng lên tier Đầy đủ (MVP) vì Adaptive Learning Engine (Module 0) — nơi hai bảng này phục vụ trực tiếp — nay là module lõi bắt buộc; bài tập Rearrange the Block (Thử nghiệm giới hạn) chỉ là một tính năng tiêu thụ dữ liệu từ hai bảng đã có sẵn, không kéo theo việc phải nâng tier của toàn bộ subsystem.*

### 10.3. Các điểm dữ liệu cần giữ nhất quán khi trình bày

- `conversation_turns` lưu cùng lúc điểm phát âm, ý định giao tiếp, lịch sự, và (nếu có) cụm từ/slang được gợi ý trên một lượt nói; đây là thiết kế hợp với mô hình turn-based. Bổ sung cột `stt_provider_used` (enum `'azure'` | `'whisper'`) để theo dõi provider STT thực tế xử lý lượt nói đó — phục vụ giám sát tần suất fallback (mục 9.4).
- `generated_passages` tách riêng cho Skim & Scan để không ép luồng này phụ thuộc `document_id`.
- `contextual_guess_attempts.vocab_item_id` nên cho phép nullable vì bài tập có thể phát sinh ngay cả khi từ chưa được lưu vào sổ.
- `user_errors` giữ trường `spaced_repetition_level` để thuật toán ưu tiên ôn tập đọc xuyên suốt cả 4 kỹ năng; đồng thời là nguồn nội dung ưu tiên cho bài tập Rearrange the Block ở Đọc và Viết.
- `quiz_attempts` được tái sử dụng làm nhật ký lượt làm bài Rearrange the Block, tránh tạo thêm bảng lượt-làm-bài riêng cho tính năng này.
- `movie_context_tts_fallback` là nhánh dự phòng hợp lệ, dùng mẫu câu đọc bằng TTS nếu chưa có video thật phù hợp.
- `vocab_items.document_id` giữ nguyên nullable như thiết kế gốc; khi từ vựng đến từ extension, trường này để trống và ngữ cảnh nguồn được lưu riêng ở `source_url`, tránh nhầm lẫn với luồng RAG thật của Notebook.
- `refresh_tokens` vốn không có ràng buộc unique theo `user_id`, nên việc hỗ trợ nhiều client (web + extension) đăng nhập song song không đòi hỏi thay đổi cấu trúc, chỉ cần bổ sung cột `client_type` để truy vấn/thu hồi theo từng loại client khi cần.
- `user_phrasebook_entries.slang_phrase_id` và `user_phrasebook_entries.conversation_turn_id` đều nullable độc lập nhau: một bản ghi có thể chỉ có một trong hai (ví dụ cụm từ LLM sinh mới không nằm trong thư viện, hoặc người học lưu trực tiếp từ thư viện mà không qua hội thoại).
- `writing_submissions` bổ sung 3 cột phục vụ 3 nguồn đề bài (Summary/Extended Topic/Free Topic): `source_type` (enum), `prompt_text` (đề bài cụ thể được chọn/sinh ra, lưu lại để hiển thị và tái sử dụng), `certificate_style` (nullable, chỉ set khi đề được sinh qua gợi ý phong cách chứng chỉ). `source_type = 'extended_topic'`/`'free_topic'` không dùng `document_chunks` làm ground truth chấm coverage như `'document_summary'` — 2 loại này chấm theo 1 rubric chung 4 tiêu chí thay thế (chi tiết mục 9.7 và `docs/feature-writing.md` mục 1).

### 10.4. Cách dùng tài liệu dữ liệu và ERD

`thiet_ke_database.md` và `erd.mermaid` là hai tài liệu nguồn cho phần dữ liệu. Phần mô tả trong file hợp nhất này chỉ giữ mức khái quát để thống nhất câu chữ giữa đề cương, kiến trúc và schema, tránh lặp lại toàn bộ bảng ở nhiều nơi.

## 11. Các điểm còn mở nhưng đã được giới hạn phạm vi

- Phần chấm điểm ý định giao tiếp và lịch sự trong hội thoại AI vẫn cần hoàn thiện prompt/logic cụ thể, nên được trình bày là phần đang hoàn thiện chứ chưa khẳng định đã tối ưu.
- Giá trị cụ thể của enum `error_type` (dùng cho bảng `user_errors`, phục vụ phân loại lỗi trong Adaptive Learning Engine và bài tập Rearrange the Block) chưa được chốt tại thời điểm viết đề cương — cần hoàn thiện trước khi chạy migration Alembic cho bảng này.
- Thư viện `slang_phrases` cần xác định quy mô ban đầu (số lượng cụm từ, tiêu chí chọn nguồn tham chiếu) trước khi triển khai Module 4 — hiện chỉ mới thống nhất về cấu trúc bảng, chưa chốt nội dung seed data.
- Movie Delivery Context tách 2 tier: nhánh TTS fallback (`movie_context_tts_fallback`) ở Thử nghiệm giới hạn, triển khai cuối Giai đoạn 8 (mục 8); nhánh tìm video thật vẫn Định hướng mở rộng, chưa khả thi trong phạm vi khóa luận hiện tại. Cần chuẩn bị trả lời câu hỏi phản biện về giá trị khác biệt của nhánh TTS fallback so với các chức năng sinh câu ví dụ + TTS đã có ở module khác, khi chưa có nhánh video thật đi kèm.
- Chế độ voice-to-voice thời gian thực và video streaming quy mô lớn đều được xếp vào hướng phát triển sau.
- Nhánh Extension tra từ trong phụ đề video (Định hướng mở rộng) phụ thuộc cấu trúc DOM/caption track của YouTube, dễ vỡ khi nền tảng bên thứ ba thay đổi giao diện — cần trình bày rõ đây là proof-of-concept minh họa khả năng mở rộng, không phải cấu phần được cam kết vận hành ổn định lâu dài trong phạm vi khóa luận.
- Ý nghĩa cụ thể của phong cách đề `cambridge` trong tính năng chọn đề bài Viết (mục 9.7) chưa được xác nhận: hiện đang hiểu là phong cách **Cambridge English Writing** (FCE/CAE) để nhất quán với việc đây là bài tập viết luận; cần xác nhận lại nếu ý định ban đầu là dùng cấu trúc đề Reading của Cambridge làm nguồn cảm hứng chủ đề.
