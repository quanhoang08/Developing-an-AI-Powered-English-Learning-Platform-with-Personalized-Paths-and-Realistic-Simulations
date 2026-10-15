# Thực nghiệm bộ chấm Writing (12 bài tự soạn x lần chạy lặp, rubric 4 tiêu chí kiểu IELTS Task 2)

Mức A2/B1/B2/C1 của bài do người soạn gán (chưa có giám khảo người xác nhận). Spearman = tương quan hạng giữa mức gán và điểm tổng; 'Tăng nghiêm ngặt' = số nhóm (đề, lần chạy) có điểm A2<B1<B2<C1; SD = độ lệch chuẩn điểm tổng giữa các lần chạy lặp cùng một bài (điểm 0-100).

| Model | Lần gọi (lỗi) | Spearman | Tăng nghiêm ngặt | Tăng không giảm | SD TB | Biên độ TB | CEFR đúng | CEFR ±1 mức | Điểm TB A2/B1/B2/C1 | Giây/bài |
|---|---|---|---|---|---|---|---|---|---|---|
| gemma3:4b | 36 (2) | 0.94 | 5/8 | 8/8 | 0.60 | 1.33 | 74% | 100% | 51.6 / 67.4 / 78.7 / 81.2 | 63.0 |
| llama3.1:8b | 36 (0) | 0.94 | 8/9 | 9/9 | 5.12 | 12.17 | 61% | 100% | 30.7 / 54.2 / 80.9 / 87.8 | 44.3 |
| qwen2.5:7b-instruct-q4_K_M | 36 (2) | 0.89 | 4/7 | 5/7 | 2.33 | 5.25 | 32% | 94% | 57.7 / 75.9 / 83.8 / 85.0 | 43.2 |
| qwen3:4b-instruct-2507-q4_K_M | 36 (2) | 0.97 | 7/7 | 7/7 | 2.70 | 6.17 | 68% | 100% | 39.3 / 63.3 / 85.1 / 91.0 | 49.1 |
