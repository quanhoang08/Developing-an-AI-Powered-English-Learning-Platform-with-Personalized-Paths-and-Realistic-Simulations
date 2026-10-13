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

### 2.2 Các model khác (cùng bộ bài, cùng 3 lần chạy)

*(Điền khi chạy xong — xem mục 4.)*

## 3. Cải thiện Ollama trên GPU 6 GB — thử hai model 4B mới

Bối cảnh: model 7B (5,8 GB khi nạp) chỉ nằm ~70% trên GPU, phần còn lại phải chạy bằng CPU nên chậm (tra từ ~10 giây, quiz ~21 giây theo `small_model.md`). Hướng thử: model ~4B vừa trọn GPU (gemma3:4b 3,4 GB; qwen3:4b-instruct-2507 2,5 GB), dùng đúng bộ benchmark đã có (tra từ 40 ca × 2 lần, quiz thích ứng 13 kịch bản, chấm Writing 12 bài × 3 lần). Tiêu chí quyết định đổi model mặc định: **không kém Qwen 7B về chất lượng** (tra từ nghĩa đúng ≥ 79%, quiz đủ số câu ≥ 92%, Writing Spearman ≥ 0,85) và nhanh hơn rõ rệt.

*(Kết quả điền ở mục 4.)*

## 4. Kết quả chạy model mới

*(Đang chạy lúc viết tài liệu này; sẽ cập nhật ngay khi xong.)*
