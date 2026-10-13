# Thực nghiệm bộ đếm cấu trúc câu (luật, không LLM): 40 câu tự viết và tự gán nhãn

**Độ chính xác loại câu: 38/40 (95%)**

## Ma trận nhầm lẫn (hàng = nhãn đúng, cột = luật dự đoán)

| | simple | compound | complex | compound_complex | Recall |
|---|---|---|---|---|---|
| simple | 14 | 0 | 0 | 0 | 14/14 (100%) |
| compound | 1 | 9 | 0 | 0 | 9/10 (90%) |
| complex | 1 | 0 | 9 | 0 | 9/10 (90%) |
| compound_complex | 0 | 0 | 0 | 6 | 6/6 (100%) |

## Cấu trúc nâng cao

| Cấu trúc | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|
| conditional | 3 | 0 | 0 | 100% | 100% |
| passive | 5 | 3 | 0 | 62% | 100% |
| relative_clause | 3 | 0 | 0 | 100% | 100% |
| question | 2 | 0 | 0 | 100% | 100% |

## Các câu luật nhận sai

- "Prices rose sharply and the government acted quickly." — đúng: compound, luật: simple
- "She said that she was tired." — đúng: complex, luật: simple

Hạn chế: bộ câu nhỏ (40) do chính tác giả viết nên không đại diện cho văn bản người học thật; luật dùng regex nên bỏ sót mệnh đề 'that' và chủ ngữ dài sau liên từ (xem ponytail trong text_metrics.py). Lần chạy đầu cho passive precision 38%; rà 5 dương tính giả thì 2 câu ('was cancelled', 'was closed') là bị động thật do tác giả gán thiếu nhãn (đã sửa nhãn), 3 câu còn lại là tính từ 'tired' bị luật nhầm là bị động — lỗi thật của luật.
