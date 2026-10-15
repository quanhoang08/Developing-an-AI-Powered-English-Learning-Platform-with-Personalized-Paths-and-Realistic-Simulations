# Thực nghiệm định lượng bổ sung (2026-10-13)

> Bổ sung cho `thuc_nghiem_rag_ollama.md` (RAG, model nhỏ cho tra từ/quiz). Mã và dữ liệu thô: `backend/experiments/` (`run_writing_eval.py`, `writing_eval_set.json`, `run_structure_eval.py`, `results/`). Máy: RTX 4050 Laptop 6 GB, Ollama, mô hình lượng tử hóa 4 bit.

## ⚠️ Điều phải nói rõ khi đưa vào báo cáo

- **Cả hai bộ dữ liệu dưới đây do trợ lý AI (Claude) soạn, không phải bài của người học thật và không phải do giám khảo chấm.** Bộ 12 bài Writing có mức A2/B1/B2/C1 do người soạn *gán* theo độ phức tạp cú pháp/vốn từ/mật độ lỗi; bộ 40 câu cấu trúc câu được gán nhãn bởi chính người viết câu. Vì vậy các số liệu chỉ đo **độ ổn định và độ phân biệt** của bộ chấm, KHÔNG đo độ chính xác tuyệt đối so với giám khảo thật. Nếu có thể, nhờ giảng viên/giáo viên tiếng Anh chấm lại 12 bài (hoặc gán lại mức) để có chuẩn con người.
- Khi chạy lần đầu, 2 câu của bộ cấu trúc câu bị gán thiếu nhãn "bị động"; đã rà các dương tính giả, sửa nhãn và ghi lại điều này ngay trong `results/structure_eval.md` — báo cáo nên ghi trung thực việc nhãn được sửa sau lần chạy đầu.
- Các lần chạy diễn ra cùng lúc với job dựng ngân hàng đề (cũng dùng Ollama/GPU) nên cột "giây/bài" bị nhiễu; chỉ so sánh chất lượng, không so sánh tốc độ.

## 1. Bộ đếm cấu trúc câu bằng luật (không LLM) — `app/utils/text_metrics.sentence_structures`

40 câu (14 đơn, 10 ghép, 10 phức, 6 ghép-phức; có câu hỏi, bị động, quan hệ, điều kiện). Kết quả (`results/structure_eval.md`):

| Chỉ số | Kết quả |
|---|---|
| Độ chính xác loại câu | **38/40 (95%)** |
| Recall: đơn / ghép / phức / ghép-phức | 100% / 90% / 90% / 100% |
| Điều kiện, quan hệ (who/which/whose), câu hỏi | precision 100%, recall 100% |
| Bị động | recall 100%, **precision 62%** (5 đúng, 3 sai) |

Lỗi thật của luật (đáng nêu trong phần hạn chế):
1. *"She said that she was tired."* → luật coi là câu đơn (không nhận mệnh đề `that`).
2. *"Prices rose sharply and the government acted quickly."* → bỏ sót câu ghép khi chủ ngữ thứ hai là cụm danh từ và động từ không phải trợ động từ.
3. Tính từ phân từ như *"tired"* (*"He is tired"*, *"he was tired"*) bị nhận nhầm là bị động — nguyên nhân của 3/8 dương tính giả.

Kết luận: dùng được làm chỉ báo thô độ đa dạng cấu trúc (đúng với ghi chú `ponytail` trong mã), không nên dùng để chấm điểm.

## 2. Bộ chấm Writing (`llm_service.grade_open_essay`, rubric 4 tiêu chí kiểu IELTS Task 2)

Thiết kế: 12 bài (3 đề × 4 mức), mỗi bài chấm 3 lần ở cùng cấu hình thật của ứng dụng (chỉ đổi `ollama_model_name`). Chỉ số: Spearman giữa mức gán và điểm tổng; số nhóm (đề, lần chạy) mà điểm tăng đúng thứ tự A2<B1<B2<C1; SD điểm giữa các lần chạy lặp cùng một bài; độ khớp nhãn CEFR.

### 2.1 Qwen 2.5 7B (mô hình mặc định) — `results/writing_eval.md`

| Chỉ số | Kết quả |
|---|---|
| Số lần gọi (lỗi) | 36 (2 lỗi, chưa phân loại nguyên nhân) |
| Spearman (mức gán, điểm tổng) | **0,89** |
| Điểm tăng đúng thứ tự A2<B1<B2<C1 | nghiêm ngặt 4/7 nhóm; không giảm 5/7 nhóm |
| Độ ổn định giữa lần chạy lặp | SD trung bình **2,3 điểm** (biên độ trung bình 5,3 điểm / 100) |
| Nhãn CEFR đúng chính xác / lệch ≤ 1 mức | **32% / 94%** |
| Điểm trung bình theo mức gán A2 / B1 / B2 / C1 | **57,7 / 75,9 / 83,8 / 85,0** |

Đọc kết quả:
- **Xếp hạng tốt, hiệu chuẩn kém.** Bộ chấm phân biệt rõ A2 với B1/B2 (Spearman 0,89, SD thấp) nhưng **chấm quá dễ**: bài A2 (có nhiều lỗi ngữ pháp rõ) vẫn được ~58/100, còn B2 và C1 gần như không phân biệt (83,8 so với 85,0) → hiệu ứng trần ở nhóm điểm cao.
- Nhãn CEFR chỉ đúng chính xác 32%; chấp nhận lệch một mức mới đạt 94%. Vì vậy nhãn CEFR/band mà ứng dụng hiện hiển thị chỉ nên coi là ước lượng (khớp với cách báo cáo mô tả band IELTS/CEFR là "ước lượng").
- Độ lệch giữa các lần chấm lặp nhỏ (≈2 điểm) → chấm lại cùng một bài không đổi kết quả đáng kể ở nhiệt độ mặc định.

### 2.2 Llama 3.1 8B (mô hình chấm riêng `OLLAMA_JUDGE_MODEL_NAME`) so với Qwen 2.5 7B — cùng bộ bài, cùng 3 lần chạy

| Chỉ số | Qwen 2.5 7B (đang dùng chấm Writing) | Llama 3.1 8B |
|---|---|---|
| Số lần gọi (lỗi) | 36 (2) | 36 (0) |
| Spearman | 0,89 | **0,94** |
| Tăng đúng thứ tự A2<B1<B2<C1 (nghiêm ngặt) | 4/7 nhóm | **8/9 nhóm** |
| SD giữa lần chạy lặp / biên độ | **2,3** / **5,3** | 5,1 / 12,2 |
| Nhãn CEFR đúng chính xác / lệch ≤ 1 mức | 32% / 94% | **61% / 100%** |
| Điểm TB A2 / B1 / B2 / C1 | 57,7 / 75,9 / 83,8 / 85,0 | **30,7 / 54,2 / 80,9 / 87,8** |

Thêm **Gemma 3 4B** (model 3,4 GB, vừa trọn GPU 6 GB), cùng bộ bài và 3 lần chạy: 36 lần gọi (2 lỗi), Spearman **0,94**, tăng đúng thứ tự nghiêm ngặt 5/8 nhóm (không giảm 8/8), SD giữa lần chạy lặp chỉ **0,6** (biên độ 1,3 — ổn định nhất), nhãn CEFR đúng chính xác **74%** và lệch ≤ 1 mức **100%**, điểm trung bình A2 / B1 / B2 / C1 = 51,6 / 67,4 / 78,7 / 81,2 (bài A2 vẫn được hơi cao và B2/C1 ít tách nhau). Cột "giây/bài" 63 giây bị nhiễu vì chạy cùng job dựng đề trên GPU, không dùng để so tốc độ.

Thêm **Qwen3 4B instruct-2507** (2,5 GB): 36 lần gọi (2 lỗi), Spearman **0,97** (cao nhất), tăng đúng thứ tự nghiêm ngặt **7/7** nhóm, SD 2,7 (biên độ 6,2), nhãn CEFR đúng chính xác 68% và lệch ≤ 1 mức 100%, điểm trung bình A2 / B1 / B2 / C1 = **39,3 / 63,3 / 85,1 / 91,0** (tách mức rõ nhất, hiệu chuẩn tốt hơn Qwen 2.5 7B).

Đọc kết quả: Llama phân biệt mức tốt hơn rõ (bài A2 ~31 điểm thay vì ~58, B2 và C1 tách được; CEFR chính xác gần gấp đôi, không lỗi), nhưng kém ổn định hơn giữa các lần chấm lặp (SD 5,1 so với 2,3). Hiện `grade_open_essay` dùng mô hình mặc định (Qwen) chứ không dùng mô hình chấm riêng; đổi sang Llama là một thay đổi nhỏ nhưng làm model luân phiên trong 6 GB GPU (Llama 8B chỉ nằm ~57% trên GPU), nên chưa đổi — xem quyết định ở cuối tài liệu này. Giới hạn như mục đầu: bộ bài do AI soạn và gán mức.

## 3. Cải thiện Ollama trên GPU 6 GB — thử hai model 4B mới

Bối cảnh: model 7B (5,8 GB khi nạp) chỉ nằm ~70% trên GPU, phần còn lại phải chạy bằng CPU nên chậm (tra từ ~10 giây, quiz ~21 giây theo `small_model.md`). Hướng thử: model ~4B vừa trọn GPU (gemma3:4b 3,4 GB; qwen3:4b-instruct-2507 2,5 GB), dùng đúng bộ benchmark đã có (tra từ 40 ca × 2 lần, quiz thích ứng 13 kịch bản, chấm Writing 12 bài × 3 lần). Tiêu chí quyết định đổi model mặc định: **không kém Qwen 7B về chất lượng** (tra từ nghĩa đúng ≥ 79%, quiz đủ số câu ≥ 92%, Writing Spearman ≥ 0,85) và nhanh hơn rõ rệt.

*(Kết quả điền ở mục 4.)*

## 4. Kết quả chạy model mới

Cùng bộ benchmark `run_small_model.py` đã dùng ở `thuc_nghiem_rag_ollama.md` (tra từ 40 ca × 2 lần; quiz thích ứng 13 kịch bản), thêm hai model 4B. Số liệu thô: `backend/experiments/results/small_model/`, bảng đầy đủ `results/small_model.md`.

| Chỉ số | Qwen 2.5 7B (mặc định) | Gemma3 4B | Qwen3 4B instruct |
|---|---|---|---|
| Tra từ: lượt thành công | **100%** | 49% | 89% |
| Tra từ: nghĩa đầu tiên đúng (trên 80 lượt) | **79%** | 44% | 71% |
| Tra từ: từ đa nghĩa đúng | **66%** | 38% | 66% |
| Tra từ: thời gian TB / p95 (giây) | **9,9 / 13,9** | 33,8 / 86,3 | 35,2 / 120,1 |
| Quiz: đủ số câu yêu cầu | 92% | **100%** | 85% |
| Quiz: lựa chọn không trùng nhau | **98%** | 84% | 90% |
| Quiz: đáp án khớp mô hình 7B chấm | **88%** | 78% | 43% |
| Quiz: thời gian TB (giây) | 20,8 | 74,2 | **11,3** |
| Chấm Writing: Spearman / CEFR đúng chính xác | 0,89 / 32% | 0,94 / 74% | **0,97** / 68% |

**Kết luận: giữ Qwen 2.5 7B làm mô hình mặc định cho tra từ và quiz; chưa đổi.**
- Tra từ: không model 4B nào đạt Qwen 7B. Gemma3 chỉ thành công 49% (nhiều lượt hết thời gian chờ hoặc "ai_unavailable"); Qwen3 đạt 71% nhưng vẫn có lượt hết thời gian chờ.
- Quiz: Qwen3 4B nhanh nhất (11 giây) nhưng đáp án chỉ khớp bộ chấm 43% và đáp án đúng dồn vào vị trí A (24/49), nên chất lượng câu hỏi đáng ngờ. Gemma3 đủ câu 100% nhưng đáp án khớp chỉ 78% và rất chậm trong lần đo này.
- Điểm sáng duy nhất: **chấm Writing** — Qwen3 4B và Gemma3 4B xếp hạng bài tốt hơn Qwen 7B (mục 2). Đây là ứng viên thay model cho riêng tác vụ Writing, cần đo thêm (nhất là độ ổn định, vì mỗi model có 2/36 lần lỗi).

**Giới hạn quan trọng — không dùng cột thời gian và tỉ lệ thành công của tra từ để kết luận cuối:** trong lúc chạy, GPU còn bị chia với job dựng ngân hàng đề TOEIC (cũng gọi Ollama), nên các lượt hết thời gian chờ 120 giây và thời gian trung bình của hai model 4B bị thổi phồng (Gemma3 74 giây cho quiz so với 8–11 giây ở model cùng cỡ khi GPU rảnh). Cột chất lượng của các lượt thành công đáng tin hơn. Muốn có phép so sánh sạch phải dừng job dựng đề rồi chạy lại. Ngoài ra, bộ chấm đáp án quiz ("khớp mô hình 7B") do chính Qwen 7B làm nên thiên lệch có lợi cho 7B (hạn chế đã nêu ở báo cáo mục 6.3.5).

## 3. Kiểm chứng lại trên dữ liệu thật (2026-10-13)

Hai bộ tự soạn ở trên được thay/bổ sung bằng dữ liệu của bên thứ ba. **Kết quả thật kém hơn nhiều so với bộ AI tự soạn; các số 95% (cấu trúc câu) và Spearman 0,97 (Writing) ở trên không nên dùng làm kết luận chính.**

### 3.1 Cấu trúc câu — Universal Dependencies English-EWT (CC BY-SA 4.0), `experiments/run_structure_eval_ud.py`
993 câu thật. Nhãn đơn/ghép/phức/ghép-phức được **suy ra bằng luật** từ cây cú pháp do người chú thích (người không gán trực tiếp loại câu). Kết quả (`results/structure_eval_ud.md`): đúng **75%** (740/993); recall câu đơn 93%, ghép 68%, **phức 41%**, ghép-phức 41%; mệnh đề quan hệ recall 30%, bị động precision 86%/recall 70%, điều kiện và câu hỏi tốt. Lỗi chính: bỏ sót mệnh đề `that` và mệnh đề quan hệ trong câu dài. Kết luận "chỉ báo thô, không dùng để chấm điểm" vẫn đúng và nên nhấn mạnh hơn.

### 3.2 Chấm Writing — bài thật của người học, Cambridge English Write & Improve (BEA-2019), `experiments/make_bea_set.py`
40 bài (10 bài/mức A2, B1, B2, C1; 120–300 từ; seed 42), mức CEFR do người chú thích của Cambridge gán. Model: qwen3:4b-instruct-2507 (model Writing hiện tại), 1 lần chạy, `results/writing_eval_bea.md`:

| Chỉ số | Bộ AI tự soạn (mục 2) | Bài thật BEA |
|---|---|---|
| Spearman (mức, điểm) | 0,97 | **0,37** |
| Điểm TB A2/B1/B2/C1 | tách rõ | 48 / 53 / 53 / 56 |
| CEFR đúng / ±1 mức | - | 29% / 74% |
| Lỗi | - | 2/40 (1 hết thời gian chờ) |

So sánh 3 model trên cùng 40 bài thật (1 lần chạy mỗi model):

| Model | Spearman | CEFR đúng | CEFR ±1 mức | Điểm TB A2/B1/B2/C1 | Lỗi |
|---|---|---|---|---|---|
| qwen3:4b-instruct-2507 | 0,37 | 29% | 74% | 48 / 53 / 53 / 56 | 2 |
| qwen2.5:7b-instruct | 0,33 | 22% | 82% | 62 / 66 / 65 / 70 | 0 |
| llama3.1:8b | 0,27 | 23% | 77% | 43 / 45 / 51 / 53 | 1 |

Cả ba đều chỉ xếp hạng yếu (Spearman 0,27–0,37), chênh nhau nằm trong sai số của mẫu 40 bài nên **không kết luận được model nào chấm tốt hơn**; thứ hạng khác hẳn bộ AI tự soạn (Qwen3 > Llama > Qwen 7B). Điểm tuyệt đối khác nhau nhiều (Qwen 7B chấm cao hơn ~15 điểm) nhưng chênh giữa các mức đều nhỏ.

**Độ ổn định trên bài thật (Qwen3 4B, 3 lần chạy lặp × 40 bài, chạy riêng một lượt sau các lượt 1-lần ở trên; `--repeats 3`):** 120 lần gọi, 9 lỗi (cả 9 là `ollama_timeout`). Spearman gộp 0,31, nhưng **từng lượt chạy rất khác nhau: 0,27 / 0,17 / 0,48**; lượt 1-lần trước đó cho 0,37, nên con số 0,37 ở bảng trên chỉ là một mẫu trong khoảng này. Độ lệch chuẩn điểm giữa các lần chấm lặp cùng một bài trung bình **3,6–3,9 điểm** (33 bài có đủ 3 điểm), biên độ trung bình 8,7 điểm; 10/33 bài chênh từ 10 điểm trở lên, lớn nhất 35 điểm. CEFR đúng 26%, sai không quá một mức 69%. Điểm TB A2/B1/B2/C1 = 48 / 52 / 57 / 55 (B2 > C1). Tức là Qwen3 4B kém ổn định hơn trên bài thật so với số SD 2,3 của Qwen 7B trên bộ AI tự soạn (mục 2.1), và chênh lệch giữa các model ở bảng 3 model trên (Spearman 0,27–0,37) nhỏ hơn dao động giữa các lần chạy của chính một model. Hai model còn lại chưa chạy lặp.

Bộ chấm phân biệt thô được bài yếu và bài mạnh nhưng gần như không tách B1/B2/C1 trên bài thật; có bài B2 bị chấm 5 điểm. Giới hạn: đề gốc không có trong dữ liệu nên dùng một đề chung (tiêu chí bám đề bị ảnh hưởng); bài là thư/truyện/ý kiến chứ không chỉ Task 2; chỉ 1 lần chạy, 1 model; dữ liệu BEA chỉ dùng phi thương mại, không đưa vào repo (đã `.gitignore`).

### 3.3 Slang — xem `docs/doi_chieu_slang_tu_dien.md`
42/80 cụm đối chiếu được với Oxford Learner's Dictionaries/Wiktionary; Cambridge và Merriam-Webster chặn truy cập tự động nên chưa kiểm chứng phần còn lại.

### 3.4 Tốc độ model — đo sạch (2026-10-13)
Đo bằng bộ đếm thời gian của chính Ollama (`/api/generate`, `temperature 0`, 200 token sinh, 1 bài BEA cố định làm prompt, 1 lần nguội + 5 lần nóng mỗi model). Trước **mỗi** lần gọi: GPU 0% và không có model nào khác đang nạp (đã dỡ hết model trước mỗi lượt). Một job Gemini của phiên khác vẫn chạy nên không dùng GPU; Epic Games Launcher có mặt trên GPU nhưng ở 0%.

| Model | Nạp nguội (s) | Tốc độ sinh, trung vị 5 lần nóng (token/s) | Khoảng | Prompt (token/s) | VRAM / kích thước (GB) |
|---|---|---|---|---|---|
| qwen3:4b-instruct-2507-q4_K_M | 13.9 (nạp 6.8) | 41.0 | 38.9–41.8 | 2498 | 4.25 / 5.35 |
| gemma3:4b | 15.6 (nạp 9.0) | 46.5 | 45.4–48.3 | 985 | 3.18 / 4.02 |
| qwen2.5:7b-instruct-q4_K_M | 22.3 (nạp 9.9) | 20.0 | 16.3–20.5 | 1933 | 4.09 / 5.83 |

Đọc kết quả: Gemma3 4B nhanh hơn Qwen3 4B khoảng 12%, cả hai nhanh gấp đôi Qwen 2.5 7B (7B không nằm trọn trong GPU 6 GB). Chênh nhau giữa các lần nóng nhỏ (trừ một lần 16,3 token/s của Qwen 7B). Thời gian 40–50 giây/bài trong bảng BEA ở mục 3.2 **không phải tốc độ model**: gọi `grade_open_essay` thật mất 49,5 giây cho một bài trong khi sinh 200 token chỉ mất ~7 giây; nguyên nhân chưa được đo (nhiều khả năng đầu ra chấm điểm dài hơn 200 token và/hoặc có gọi lặp; chưa kiểm số token thực tế) (cột "Giây/bài" ở mục 3.2 cần bỏ qua).

### 3.5 Xác nhận đường chấm Writing thật dùng Qwen3
Gọi `llm_service.grade_open_essay` trong container api **không ghi đè cấu hình**: `ollama_writing_model_name = qwen3:4b-instruct-2507-q4_K_M`, `ollama_model_name = qwen2.5:7b-instruct-q4_K_M`. Trong lúc gọi, `/api/ps` của Ollama chỉ thấy `qwen3:4b-instruct-2507-q4_K_M` được nạp (49,5 giây, điểm 55, CEFR B1). Lưu ý: đây chỉ xác nhận cho cấu hình mặc định hiện tại, không xác nhận cho môi trường khác ghi đè `OLLAMA_WRITING_MODEL_NAME`.
