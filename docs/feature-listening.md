# Feature Spec — Module 2: Nghe (Listening)

> Nguồn đối chiếu: `de_cuong_khoa_luan.md` mục 5.2, `thiet_ke_database.md` mục 1.
> Bảng liên quan chính: `documents`, `podcasts`, `transcript_segments`, `dictation_attempts`, `personas`, `quiz_attempts`, `user_errors`.

---

## 1. Podcast tự động từ tài liệu (Đầy đủ)

### 1.1 Mục tiêu
Chuyển nội dung tài liệu người dùng (audio hoặc .docx đã có transcript/text) thành 1 podcast nghe được, có transcript đồng bộ theo từ.

### 1.2 Input
- `document_id` (bắt buộc, phải `status = 'ready'`).
- `persona_id` (tuỳ chọn — giọng đọc; mặc định lấy persona mặc định của hệ thống nếu không chọn).

### 1.3 Flow
1. Nếu tài liệu gốc là **audio**: dùng trực tiếp file audio đã upload (không cần TTS lại) — Podcast = chính bản ghi âm gốc, chỉ bổ sung transcript đồng bộ.
2. Nếu tài liệu gốc là **.docx**: text được tóm tắt/biên tập lại cho phù hợp văn nói (không đọc nguyên văn học thuật) qua Gemini, sau đó gọi ElevenLabs TTS với `persona_id` để sinh audio.
3. Chạy STT (nếu audio gốc chưa có transcript) hoặc dùng timestamp trả về từ TTS provider để có `transcript_segments` (mỗi dòng: `text`, `start_ms`, `end_ms`).
4. Lưu `podcasts` (`document_id`, `audio_url`, `persona_id` nếu có).

### 1.4 Business rules
- Tài liệu audio gốc: **không** chạy lại qua TTS — giữ nguyên giọng thật của người dùng tải lên, chỉ bổ sung transcript. Đây là điểm khác biệt quan trọng cần làm rõ khi trình bày (Podcast không phải lúc nào cũng là "giọng AI đọc").
- Tài liệu .docx: bắt buộc qua bước biên tập lại văn phong trước khi TTS (không đọc thẳng văn bản gốc dạng báo cáo/học thuật — trải nghiệm nghe sẽ kém).

### 1.5 Edge cases
- Audio gốc quá dài (> giới hạn xử lý STT của Azure trong 1 lần gọi): chia nhỏ theo đoạn, ghép lại `transcript_segments` theo `start_ms` liên tục.
- `persona_id` không hợp lệ hoặc không active: fallback về persona mặc định, không lỗi cứng.

### 1.6 Acceptance criteria
- [ ] Với tài liệu audio gốc, `podcasts.audio_url` trỏ đúng file gốc, không phải file TTS mới.
- [ ] `transcript_segments` phủ toàn bộ độ dài audio, không có khoảng trống > 3 giây không giải thích được (nhạc nền/im lặng nên gộp segment liền kề, không để trống).

---

## 2. Transcript tương tác đồng bộ theo từ (Đầy đủ)

### 2.1 Mục tiêu
Khi nghe podcast, transcript highlight đúng từ đang phát, cho phép click từ để tra nghĩa ngay (tái sử dụng luồng tra từ ở Module 1 mục 3).

### 2.2 Input
- `GET /api/listening/podcasts/{podcast_id}/transcript`: không cần thêm input ngoài JWT.

### 2.3 Flow
1. Trả về `transcript_segments` sắp xếp theo `start_ms` tăng dần.
2. Client dùng `start_ms`/`end_ms` của từng segment để đồng bộ highlight theo vị trí phát audio hiện tại (`currentTime` phía client).
3. Click 1 từ trong transcript → gọi lại API tra từ (`feature-reading.md` mục 3.2), truyền `context_sentence` là câu chứa từ đó trong transcript, `source_document_id = podcasts.document_id`.

### 2.4 Business rules
- Đơn vị đồng bộ tối thiểu là **cấp từ**, không phải cấp câu — nếu ElevenLabs/STT chỉ trả timestamp cấp câu, backend cần chia nhỏ theo tỷ lệ độ dài ký tự trong câu để ước lượng timestamp từng từ (chấp nhận sai số nhỏ, ghi rõ đây là ước lượng khi trình bày khóa luận, không phải timestamp chính xác tuyệt đối).

### 2.5 Acceptance criteria
- [ ] Lệch thời gian highlight so với audio thực tế < 300ms trên tập mẫu thử nghiệm (đo thủ công).
- [ ] Click bất kỳ từ nào trong transcript đều trả về được định nghĩa (không có từ "chết" không tra được).

---

## 3. Dictation — chấm lỗi tự động (Đầy đủ)

### 3.1 Mục tiêu
Người học nghe 1 đoạn ngắn (trích từ podcast) và gõ lại chính xác những gì nghe được; hệ thống chấm lỗi từng từ.

### 3.2 Input
- `podcast_id` (bắt buộc).
- `segment_range` (tuỳ chọn — chọn đoạn cụ thể; mặc định hệ thống tự chọn 1 đoạn ~15-30 giây).
- `POST /api/listening/dictation/{attempt_id}/submit`: `transcribed_text` (bắt buộc — văn bản người học gõ).

### 3.3 Flow
1. Tạo `dictation_attempts` (`podcast_id`, đoạn audio được chọn — lưu `start_ms`/`end_ms` tham chiếu tới `transcript_segments`).
2. Trả về audio đoạn đó cho client nghe (không trả text gốc).
3. Người học nộp `transcribed_text` → backend so khớp với transcript gốc bằng thuật toán diff cấp từ (word-level, không cấp ký tự — tránh chấm sai vì lỗi gõ dấu câu/viết hoa).
4. Trả về danh sách lỗi: từ thiếu, từ thừa, từ sai — ghi từng lỗi vào `user_errors` (`error_type = 'listening_comprehension'` hoặc `'spelling'` tuỳ loại sai — xem phụ lục enum ở `api-spec.md`).

### 3.4 Business rules
- Chấm **không phân biệt hoa/thường** và bỏ qua khác biệt dấu câu thuần tuý (dấu phẩy, chấm câu) — chỉ so khớp nội dung từ.
- Đồng nghĩa/viết tắt hợp lệ (ví dụ "don't" vs "do not") được xử lý qua bảng chuẩn hoá cố định trước khi diff, không dùng LLM để chấm dictation (rule-based, giữ chi phí thấp và kết quả nhất quán).

### 3.5 Edge cases

**Người học bỏ trống hoàn toàn**: toàn bộ từ trong đoạn tính là lỗi thiếu, không lỗi hệ thống.

**Đoạn audio có từ chuyên ngành/tên riêng khó nghe** — có xử lý riêng (không còn để mặc định như lỗi nghe thông thường):

Lý do cần xử lý riêng: nếu người học nghe đúng âm nhưng gõ sai chính tả một từ chuyên ngành/tên riêng chưa từng gặp, đó là **thiếu kiến thức từ vựng** (không biết mặt chữ của từ), khác bản chất với **nghe nhầm âm**. Diff word-level thuần tuý không phân biệt được 2 nguyên nhân này — nếu gộp chung vào `listening_comprehension`, dữ liệu đưa vào Adaptive Learning Engine sẽ bị lệch: hệ thống tưởng người học yếu kỹ năng nghe và ưu tiên bài luyện nghe, trong khi thứ họ thực sự cần là học thêm từ vựng đó.

**Thiết kế xử lý — 2 bước bổ sung vào flow mục 3.3:**

1. **Gắn nhãn từ hiếm/tên riêng khi tạo bài Dictation** (bổ sung vào bước 1 của flow): với các từ trong `segment_range` được chọn, backend gắn nhãn:
   - Tên riêng: viết hoa không ở đầu câu, hoặc qua NER đơn giản.
   - Từ hiếm/chuyên ngành: không nằm trong danh sách ~5.000–8.000 từ tiếng Anh thông dụng nhất (dùng danh sách tần suất có sẵn, không cần tự xây dựng).
   - Lưu kết quả vào cột mới `reference_word_tags` (JSONB, ví dụ `[{ "word": "mitochondria", "is_rare_or_proper": true }, ...]`) trên `dictation_attempts` — chỉ tính riêng cho đoạn của attempt đó. Đây là mở rộng bảng hiện có, không tạo bảng mới, đúng nguyên tắc bảo thủ về schema.

2. **Chấm theo 2 bước thay vì diff thuần tuý** (cập nhật bước 3 của flow): với mỗi từ sai/thiếu sau khi diff word-level như cũ, tính thêm **khoảng cách ngữ âm** giữa từ người học gõ và từ đúng (dùng thuật toán Metaphone/Double Metaphone — thư viện `jellyfish`, không cần LLM):
   - **Ngữ âm gần** (cùng mã Metaphone, hoặc lệch ≤ 1 ký tự) **+** từ được gắn nhãn hiếm/tên riêng → kết luận "nghe đúng, chưa biết từ" → ghi `error_type = vocabulary`.
   - **Ngữ âm gần** + từ **thông dụng** (không gắn nhãn hiếm) → lỗi chính tả thông thường → `error_type = spelling`.
   - **Ngữ âm xa** (bất kể từ hiếm hay không) → nghe nhầm âm thật sự → `error_type = listening_comprehension` (giữ nguyên như thiết kế gốc).

3. **Điểm số bài Dictation không đổi cách tính**: cả 3 trường hợp trên đều vẫn tính là sai trong điểm số (dictation đo khả năng viết lại chính xác, không miễn trừ). Điểm khác biệt duy nhất là **loại `error_type` ghi vào `user_errors`** — quyết định hướng ôn tập sau này (gợi ý học từ vựng thay vì ép luyện nghe thêm).

4. **Feedback hiển thị cho người học** — phân biệt rõ thông điệp theo `error_type`:
   - `vocabulary`: "Bạn nghe đúng nhưng có thể chưa quen từ này — lưu vào sổ từ vựng?" (kèm nút lưu nhanh, tái sử dụng luồng tra từ ở `feature-reading.md` mục 3).
   - `listening_comprehension`: "Có thể bạn nghe nhầm âm ở từ này, nghe lại đoạn để luyện tai."

**Giới hạn còn lại (ghi nhận, không xử lý trong phạm vi khóa luận)**: gắn nhãn hiện tại chỉ ở **cấp từ đơn**, chưa xử lý cụm tên riêng nhiều từ (ví dụ "Elon Musk" bị gắn nhãn tách rời từng từ) — nêu như một đơn giản hoá có chủ đích, có thể là hướng mở rộng sau này.

### 3.6 Acceptance criteria
- [ ] Diff cấp từ chính xác trên tập test có sẵn đáp án chuẩn (không sai lệch do khác biệt hoa/thường hoặc dấu câu).
- [ ] Mỗi lỗi phát hiện tạo đúng 1 dòng `user_errors`, không trùng lặp khi nộp lại cùng 1 attempt.
- [ ] Với từ được gắn nhãn hiếm/tên riêng, nếu người học gõ sai nhưng ngữ âm gần đúng (theo ngưỡng Metaphone đã định nghĩa), hệ thống ghi `error_type = vocabulary`, không ghi `listening_comprehension` — kiểm tra trên tập test cố định có chứa từ chuyên ngành/tên riêng.
- [ ] Với từ thông dụng bị nghe nhầm rõ ràng (ngữ âm xa), hệ thống vẫn ghi `error_type = listening_comprehension` như thiết kế gốc — không bị đổi cách chấm chỉ vì bổ sung tầng phân loại mới.

---

## 4. Ghi chú triển khai chung Module 2
- Toàn bộ endpoint yêu cầu JWT hợp lệ.
- `speech_service.py` là điểm gom duy nhất cho STT/TTS (nguyên tắc mục 9.2 đề cương) — router/feature service Listening không gọi thẳng Azure/ElevenLabs SDK.
- Audio input phải chuẩn hoá PCM WAV 16kHz mono trước khi vào Azure Speech SDK (áp dụng cho cả STT dùng trong Dictation nếu về sau cần chấm phát âm — hiện tại Dictation chỉ chấm nội dung text, không chấm phát âm).
