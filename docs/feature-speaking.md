# Feature Spec — Module 4: Nói (Speaking)

> Nguồn đối chiếu: `de_cuong_khoa_luan.md` mục 5.2/9.4, `thiet_ke_database.md` mục 3/6, `lumina_context.md` mục 3.3.
> Bảng liên quan chính: `scenarios`, `conversation_sessions`, `conversation_turns`, `personas`, `slang_phrases`, `user_phrasebook_entries`, `user_errors`, `realtime_conversation_metrics` (Định hướng mở rộng, không implement).
>
> ⚠️ Phần **3** và **4** của file này là **ĐỀ XUẤT** để giải quyết 2 điểm còn mở nêu trong `lumina_context.md` mục 4 (logic điểm ý định/lịch sự, seed data `slang_phrases`) — cần xác nhận với bạn/giảng viên trước khi implement, chưa phải quyết định cuối cùng như các phần còn lại của tài liệu.

---

## 1. Bạn đồng hành hội thoại AI — Turn-based (Thử nghiệm giới hạn)

### 1.1 Mục tiêu
Người học hội thoại theo lượt với AI trong tình huống mô phỏng thực tế (`scenarios`); mỗi lượt được chấm đồng thời trên 3 khía cạnh: phát âm, ý định giao tiếp, lịch sự.

### 1.2 Input
- `POST /api/speaking/sessions`: `scenario_id` (bắt buộc), `persona_id` (tuỳ chọn — giọng AI phản hồi).
- `POST /api/speaking/sessions/{session_id}/turns`: file audio (multipart, WAV/PCM hoặc định dạng client ghi âm phổ biến — backend tự chuẩn hoá).

### 1.3 Flow (đúng mô hình đã chốt — mục 9.4 đề cương, xử lý 2 nhánh song song)
1. Nhận audio 1 lượt nói → chuẩn hoá PCM WAV 16kHz mono.
2. **Nhánh A — STT + LLM**: Azure STT (ưu tiên) ra text; nếu Azure STT lỗi/timeout, retry 1 lần, nếu vẫn lỗi → **fallback sang Whisper** (OpenAI Whisper API) để lấy text (xem mục 1.4a) → gọi Gemini **một lệnh duy nhất** sinh đồng thời:
   - `response_text` (phản hồi hội thoại tiếp theo, đóng vai nhân vật trong `scenario`)
   - `intent_score` + `politeness_score` (xem mục 3 — rubric đề xuất)
   - `suggested_phrases` (gợi ý slang/cụm thoại phù hợp ngữ cảnh lượt đó, có nguồn tham chiếu — xem mục 4)
3. **Nhánh B — Pronunciation Assessment**: audio gốc (không phải qua STT text) → Azure Pronunciation Assessment chấm độ chính xác âm vị trên chính đoạn ghi âm. **Không có fallback cho nhánh này** — Whisper không có khả năng chấm âm vị, Azure vẫn là lựa chọn duy nhất (xem mục 1.4b).
4. Hai nhánh chạy song song (`asyncio.gather` hoặc tương đương), gộp kết quả vào 1 dòng `conversation_turns`.
5. `response_text` → TTS (ElevenLabs, giọng theo `persona_id` của session) → trả audio phản hồi cho client để tiếp tục lượt kế.

### 1.4 Business rules
- Nhánh A và B **độc lập dữ liệu đầu vào**: nhánh B luôn nhận audio gốc, không bao giờ nhận text đã qua STT (tránh mất thông tin ngữ điệu/phát âm cần thiết cho chấm điểm âm vị).
- Một `conversation_sessions` gắn đúng 1 `scenario_id` trong suốt vòng đời — không đổi kịch bản giữa chừng (nếu muốn đổi, tạo session mới).
- Nếu nhánh B (Azure Pronunciation Assessment) lỗi/timeout nhưng nhánh A thành công: vẫn trả phản hồi hội thoại bình thường, `pronunciation_score` để NULL kèm cờ `pronunciation_assessment_failed = true` — không chặn toàn bộ lượt hội thoại chỉ vì 1 service phụ trợ lỗi.

#### 1.4a Cơ chế fallback STT (Nhánh A) — Azure ưu tiên, Whisper dự phòng
- **Lý do chỉ nhánh A có fallback, nhánh B thì không**: nhánh A chỉ cần transcript thuần tuý để đưa vào LLM sinh phản hồi — Whisper làm được việc này tốt. Nhánh B cần chấm điểm âm vị chi tiết (phoneme-level), một khả năng chuyên biệt chỉ Azure Pronunciation Assessment có — đây là lý do "Azure bắt buộc" ban đầu trong `lumina_context.md`, và lý do đó **chỉ áp dụng cho nhánh B**, không áp dụng cho nhánh A.
- **Trình tự cụ thể**: gọi Azure STT → lỗi/timeout → retry Azure 1 lần → vẫn lỗi → gọi Whisper API lấy transcript → vẫn lỗi (cả 2 provider đều fail) → trả lỗi nghiệp vụ `stt_service_unavailable`, không tạo `conversation_turns` (giống cách xử lý `empty_transcription` ở mục 1.5).
- **Ghi lại provider đã dùng**: mỗi `conversation_turns` lưu thêm cột `stt_provider_used` (`'azure'` | `'whisper'`) — phục vụ theo dõi tần suất fallback thực tế, có thể dùng làm số liệu minh hoạ tính resilience của hệ thống khi trình bày khóa luận.
- **Fallback trong suốt với người dùng**: client không cần biết provider nào đã xử lý — response schema không đổi, chỉ khác trường `stt_provider_used` phục vụ mục đích log/thống kê nội bộ.
- **Dependency mới**: OpenAI Whisper API — phạm vi sử dụng giới hạn nghiêm ngặt trong vai trò STT dự phòng của nhánh A, không dùng cho bất kỳ mục đích nào khác (không thay LLM, không thay Pronunciation Assessment) — tránh mở rộng phạm vi ngoài lý do được thêm vào.

#### 1.4b Nhánh B — không có fallback (nhắc lại để tránh nhầm)
- Nếu Azure Pronunciation Assessment lỗi, xử lý như đã mô tả ở mục 1.4 (NULL + cờ lỗi) — **không** gọi Whisper hay bất kỳ provider nào khác để thay thế, vì không có provider nào khác có khả năng này.

### 1.5 Edge cases
- STT trả về text rỗng (audio không nghe rõ/im lặng) — **sau khi cả Azure lẫn Whisper đều đã thử**: không gọi nhánh LLM sinh phản hồi, trả lỗi nghiệp vụ `empty_transcription`, yêu cầu người học ghi âm lại — không tính là 1 lượt hợp lệ (không tạo `conversation_turns`).
- Cả Azure STT lẫn Whisper đều lỗi/timeout (2 provider cùng fail): trả lỗi nghiệp vụ `stt_service_unavailable`, không tạo `conversation_turns` (xem mục 1.4a).
- Session không hoạt động > 30 phút: coi như hết hạn, các lượt gửi lên sau đó bị từ chối, yêu cầu tạo session mới (tránh giữ context hội thoại quá cũ không còn liên quan).

### 1.6 Acceptance criteria
- [ ] Mỗi lượt hội thoại hợp lệ tạo đúng 1 dòng `conversation_turns` chứa đủ: `pronunciation_score` (hoặc NULL + cờ lỗi), `intent_score`, `politeness_score`, `response_text`, `stt_provider_used`.
- [ ] Khi Azure STT lỗi/timeout (mô phỏng bằng mock), hệ thống tự động fallback sang Whisper mà không cần người dùng thao tác lại; `stt_provider_used = 'whisper'` ghi đúng.
- [ ] Khi cả 2 provider STT đều lỗi, trả `stt_service_unavailable`, không tạo `conversation_turns` rác.
- [ ] Tổng thời gian phản hồi (ghi âm xong → nhận được audio phản hồi) được đo và log để phục vụ tiêu chí đánh giá độ trễ (mục 4 đề cương) — đo riêng cho cả 2 trường hợp `stt_provider_used = azure` và `whisper` để so sánh độ trễ giữa 2 provider khi trình bày khóa luận.
- [ ] Không có lượt nào với `transcription` rỗng được ghi vào `conversation_turns`.

---

## 2. Daily Speaking & Slang cơ bản + Sổ tay Slang/Cụm thoại (Thử nghiệm giới hạn)

### 2.1 Mục tiêu
Gợi ý cụm từ giao tiếp hàng ngày/slang phù hợp ngữ cảnh ngay trong lượt hội thoại (đã mô tả ở mục 1.3 nhánh A), và cho phép lưu lại để ôn tập.

### 2.2 Input
- `POST /api/speaking/phrasebook`: `slang_phrase_id` (nullable) **hoặc** `conversation_turn_id` (nullable) — đúng như thiết kế đã chốt, ít nhất 1 trong 2 phải có giá trị, cả hai đều nullable độc lập.
- Nếu lưu trực tiếp từ gợi ý LLM sinh tại chỗ (không nằm sẵn trong `slang_phrases`): truyền thêm `phrase_text`, `meaning`, `example_sentence` để lưu snapshot (vì cụm từ đó không có `slang_phrases.id` để tham chiếu).

### 2.3 Flow
1. Trong lượt hội thoại, `suggested_phrases` trả về gồm cả cụm từ có sẵn trong `slang_phrases` (kèm `slang_phrase_id`) lẫn cụm LLM sinh mới phù hợp ngữ cảnh cụ thể hơn (không có `slang_phrase_id`).
2. Người học bấm lưu → tạo `user_phrasebook_entries` theo đúng 1 trong 2 nguồn (mục 2.2).
3. `GET /api/speaking/phrasebook`: trả danh sách đã lưu, có thể lọc theo `formality_level`.

### 2.4 Business rules
- Validate ở service layer: `slang_phrase_id` và (`phrase_text` snapshot) không được cùng thiếu — nếu cả `slang_phrase_id` lẫn `phrase_text` đều rỗng, từ chối request (dữ liệu không đủ để hiển thị lại sau này).

### 2.5 Acceptance criteria
- [ ] Lưu cụm từ từ thư viện (`slang_phrase_id` set) hiển thị đúng thông tin gốc khi truy vấn lại sổ tay.
- [ ] Lưu cụm từ LLM sinh tại chỗ (snapshot) không bị mất dữ liệu ngay cả khi `slang_phrases` sau này không có mục tương ứng.

---

## 3. ĐỀ XUẤT — Logic chấm điểm ý định giao tiếp & lịch sự

> Trạng thái theo `lumina_context.md`/`de_cuong_khoa_luan.md` mục 11: "chưa có thiết kế prompt/logic cụ thể", cần trình bày là **phần đang hoàn thiện**, không khẳng định đã tối ưu. Đề xuất dưới đây là 1 phương án cụ thể để bắt đầu implement, không phải kết luận đã được giảng viên duyệt.

### 3.1 Đề xuất rubric

Chấm trên thang **0–100** cho mỗi khía cạnh, **trong cùng 1 lệnh gọi LLM** với phần sinh `response_text` (đúng nguyên tắc đã chốt — không tách lệnh gọi riêng):

**`intent_score`** — mức độ phản hồi của người học có đạt được mục tiêu giao tiếp của lượt thoại đó theo kịch bản (`scenarios.goal` — ví dụ: "đặt bàn nhà hàng thành công", "từ chối lời mời một cách lịch sự"). Tiêu chí chấm:
- 90-100: đạt đúng mục tiêu giao tiếp, thông tin đầy đủ, không gây hiểu lầm cho người nghe bản ngữ.
- 60-89: đạt mục tiêu nhưng thiếu thông tin phụ hoặc cách diễn đạt hơi vòng vo.
- 30-59: mục tiêu giao tiếp không rõ ràng, người nghe có thể phải hỏi lại.
- 0-29: không đạt mục tiêu giao tiếp hoặc lạc đề so với tình huống.

**`politeness_score`** — mức độ phù hợp về sự trang trọng/lịch sự **so với ngữ cảnh cụ thể của `scenario`** (quan trọng: lịch sự không phải lúc nào cũng nghĩa là trang trọng nhất — ví dụ scenario "nói chuyện với bạn thân" mà quá trang trọng cũng bị trừ điểm vì không tự nhiên). Tiêu chí chấm:
- 90-100: đúng mức độ trang trọng scenario yêu cầu, dùng đúng modal verbs/hedging phù hợp (`could you`, `would you mind`... cho tình huống trang trọng; ngôn ngữ tự nhiên, thân mật cho tình huống bạn bè).
- 60-89: về cơ bản phù hợp nhưng có 1-2 chỗ hơi cộc/hơi khách sáo không cần thiết.
- 30-59: mức trang trọng lệch rõ rệt so với ngữ cảnh (ví dụ dùng "gimme" khi nói với giáo viên).
- 0-29: thô lỗ hoặc hoàn toàn sai ngữ vực so với tình huống.

### 3.2 Đề xuất cấu trúc prompt (structured output)

```
System: Bạn là giám khảo đánh giá hội thoại tiếng Anh. Với mỗi lượt nói của người học,
trả về JSON đúng schema sau, KHÔNG kèm giải thích ngoài JSON:
{
  "response_text": string,       // phản hồi tiếp theo, đóng vai nhân vật trong scenario
  "intent_score": int,           // 0-100, theo rubric ý định giao tiếp
  "intent_feedback": string,     // 1 câu ngắn giải thích điểm
  "politeness_score": int,       // 0-100, theo rubric lịch sự
  "politeness_feedback": string, // 1 câu ngắn giải thích điểm
  "suggested_phrases": [
    { "phrase": string, "meaning": string, "source_note": string }
  ]
}

Context:
- Kịch bản: {scenario.description}
- Mục tiêu giao tiếp của lượt này: {scenario.goal}
- Mức độ trang trọng kỳ vọng: {scenario.formality_level}
- Lịch sử hội thoại: {previous_turns}
- Lượt nói vừa nhận (đã qua STT): {transcribed_text}
```

### 3.3 Business rules đề xuất
- `scenarios` cần có sẵn cột `goal` và `formality_level` để làm ground-truth chấm điểm — **cần bổ sung vào schema `scenarios` nếu chưa có** (kiểm tra lại `thiet_ke_database.md`/ERD phần `SCENARIOS` — hiện ERD chỉ có `uuid id PK`, chưa liệt kê các cột này, cần xác nhận đã có trong migration thực tế hay chỉ ERD rút gọn).
- Vì đây là phần chưa được xác nhận bằng prototype (theo `thiet_ke_database.md` mục 4), **giữ nguyên tắc `intent_score`/`politeness_score` nullable** — nếu LLM không trả về đúng schema (lỗi parse structured output), lưu NULL thay vì áng chừng giá trị mặc định, để không làm sai lệch dữ liệu đưa vào Adaptive Learning Engine.

### 3.4 Acceptance criteria đề xuất
- [ ] Trên tập hội thoại mẫu (ví dụ 20 lượt tự tạo, có đáp án tham chiếu do nhóm tự đánh giá), độ lệch giữa điểm LLM và điểm người đánh giá trong khoảng chấp nhận được (đề xuất: chênh lệch trung bình ≤ 15 điểm/100 — ngưỡng cụ thể cần thống nhất lại khi có dữ liệu thật, đây chỉ là đề xuất khởi điểm).
- [ ] Khi LLM trả JSON không đúng schema, hệ thống không crash — retry 1 lần, nếu vẫn lỗi thì lưu NULL + log để review thủ công.

---

## 4. ĐỀ XUẤT — Seed data `slang_phrases`

> Trạng thái theo context: "chỉ mới thống nhất cấu trúc bảng, chưa chốt nội dung". Đề xuất dưới đây về quy mô và tiêu chí nguồn, cần xác nhận trước khi thực sự biên soạn nội dung.

### 4.1 Đề xuất quy mô ban đầu
- **~80-120 cụm từ** cho bản seed đầu tiên (đủ để phục vụ demo Thử nghiệm giới hạn trên số lượng `scenarios` giới hạn ở tier này, không cần bao phủ toàn bộ tình huống giao tiếp).
- Phân bố theo `formality_level` đề xuất 3 mức: `casual` (~50%), `neutral` (~35%), `formal` (~15%) — vì trọng tâm tính năng là "Daily Speaking", nên ưu tiên số lượng cho `casual`/`neutral`.
- Gắn tag theo scenario liên quan (nếu `slang_phrases` có cột phân loại chủ đề — đề xuất bổ sung cột `topic_tags` nếu chưa có trong schema hiện tại, để LLM lọc gợi ý đúng ngữ cảnh thay vì gợi ý ngẫu nhiên toàn bộ thư viện).

### 4.2 Đề xuất tiêu chí chọn nguồn tham chiếu
- Ưu tiên nguồn có uy tín học thuật/từ điển được công nhận rộng rãi (ví dụ: Cambridge Dictionary, Oxford Learner's Dictionary cho phần định nghĩa chuẩn) kết hợp nguồn mô tả cách dùng thực tế đương đại (ví dụ các trang tổng hợp slang có kiểm duyệt biên tập, không dùng nguồn do người dùng tự đăng không kiểm chứng).
- Mỗi `slang_phrases` cần có: `source_reference` (tên nguồn, không phải chỉ link — để trích dẫn được trong báo cáo khóa luận), `formality_level`, `meaning`, `example_sentence`.
- **Tránh** slang có yếu tố tục tĩu/xúc phạm/nhạy cảm văn hoá — đúng tinh thần sản phẩm giáo dục, đây là tiêu chí lọc bắt buộc khi biên soạn, không phải tuỳ chọn.

### 4.3 Acceptance criteria đề xuất
- [ ] 100% bản ghi `slang_phrases` trong seed có `source_reference` không rỗng (phục vụ trích dẫn học thuật).
- [ ] Không có cụm từ nào bị gắn nhãn nội dung không phù hợp lọt qua review thủ công trước khi seed vào DB.

---

## 5. Voice-to-voice thời gian thực (Định hướng mở rộng — không implement trong phạm vi khóa luận)

Chỉ ghi chú để không nhầm phạm vi: nâng cấp tầng truyền tải (WebSocket/WebRTC, VAD, barge-in) — **không đổi logic scenario/scoring/content generation** đã mô tả ở mục 1-4. Bảng `realtime_conversation_metrics` để trống cho đến khi tier này được triển khai.

---

## 6. Ghi chú triển khai chung Module 4
- Router không gọi thẳng `speech_service`/`llm_service` — luôn qua `speaking_service.py`.
- `speech_service.py` chịu trách nhiệm ẩn logic đa provider của STT (Azure ưu tiên, Whisper fallback — mục 1.4a) sau 1 interface duy nhất; các tầng gọi phía trên (`speaking_service.py`) không cần biết provider nào đã xử lý, chỉ nhận `transcript` + `provider_used`.
- Toàn bộ endpoint yêu cầu JWT hợp lệ.
- Xem `feature-reading.md` mục 6 và `feature-writing.md` mục 4 về cách `user_errors` phát sinh từ Module 4 (nếu có — ví dụ lỗi phát âm lặp lại nhiều lần) được dùng lại cho Rearrange the Block; hiện tại **chưa có** đặc tả chi tiết việc Speaking đóng góp `user_errors` loại nào — đây là điểm nên làm rõ thêm khi implement thực tế Adaptive Learning Engine (mục 0), nằm ngoài phạm vi 5 file spec hiện tại.
