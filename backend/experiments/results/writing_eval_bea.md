# Thực nghiệm bộ chấm Writing (bài thật của người học, BEA-2019 / Cambridge Write & Improve x lần chạy lặp, rubric 4 tiêu chí kiểu IELTS Task 2)

Mức A2/B1/B2/C1 của bài: do người chú thích của Cambridge gán (BEA-2019). Spearman = tương quan hạng giữa mức gán và điểm tổng; 'Tăng nghiêm ngặt' = số nhóm (đề, lần chạy) có điểm A2<B1<B2<C1; SD = độ lệch chuẩn điểm tổng giữa các lần chạy lặp cùng một bài (điểm 0-100).

| Model | Lần gọi (lỗi) | Spearman | Tăng nghiêm ngặt | Tăng không giảm | SD TB | Biên độ TB | CEFR đúng | CEFR ±1 mức | Điểm TB A2/B1/B2/C1 | Giây/bài |
|---|---|---|---|---|---|---|---|---|---|---|
| llama3.1:8b | 40 (1) | 0.27 | 1/9 | 2/9 | - | - | 23% | 77% | 43.4 / 45.3 / 50.8 / 52.8 | 47.1 |
| qwen2.5:7b-instruct-q4_K_M | 40 (0) | 0.33 | 1/10 | 1/10 | - | - | 22% | 82% | 61.8 / 66.4 / 64.8 / 69.5 | 42.7 |
| qwen3:4b-instruct-2507-q4_K_M | 120 (9) | 0.31 | 1/22 | 2/22 | 3.88 | 8.74 | 26% | 69% | 48.4 / 51.9 / 56.7 / 55.0 | 47.0 |
