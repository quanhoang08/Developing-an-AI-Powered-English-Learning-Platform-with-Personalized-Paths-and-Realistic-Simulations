# Kết quả sinh câu trả lời — bộ GIỮ KÍN (test): 100 câu có đáp án + 40 câu ngoài tài liệu

Pipeline RAG: sentence-o1/120 từ + bge-m3, top-3. Trong ngoặc là % và khoảng tin cậy Wilson 95%.

| Biến thể | Đúng (có đáp án) | Từ chối nhầm | Từ chối đúng (ngoài tài liệu) | Đúng ngôn ngữ | Bám tài liệu* | Số từ TB | Giây/câu |
|---|---|---|---|---|---|---|---|
| qwen2.5-7b/base | 96/100 (96%, CI 90–98) | 1/100 | 32/40 (80%, CI 65–90) | 126/140 (90%, CI 84–94) | 0.715 | 15.3 | 10.1 |
| qwen2.5-7b/base+rules | 97/100 (97%, CI 92–99) | 0/100 | 35/40 (88%, CI 74–95) | 139/140 (99%, CI 96–100) | 0.752 | 16.2 | 1.1 |
| qwen2.5-7b/modelfile | 97/100 (97%, CI 92–99) | 1/100 | 33/40 (82%, CI 68–91) | 140/140 (100%, CI 97–100) | 0.747 | 17.3 | 1.2 |
| llama3.1-8b/base | 95/100 (95%, CI 89–98) | 3/100 | 38/40 (95%, CI 83–99) | 126/140 (90%, CI 84–94) | 0.78 | 13.0 | 1.2 |
| llama3.1-8b/base+rules | 97/100 (97%, CI 92–99) | 0/100 | 33/40 (82%, CI 68–91) | 139/140 (99%, CI 96–100) | 0.753 | 16.0 | 1.4 |
| llama3.1-8b/modelfile | 94/100 (94%, CI 88–97) | 0/100 | 32/40 (80%, CI 65–90) | 139/140 (99%, CI 96–100) | 0.741 | 15.9 | 1.4 |
| mistral-7b/base | 82/100 (82%, CI 73–88) | 7/100 | 32/40 (80%, CI 65–90) | 105/140 (75%, CI 67–81) | 0.558 | 27.4 | 2.2 |
| mistral-7b/base+rules | 91/100 (91%, CI 84–95) | 2/100 | 21/40 (52%, CI 37–67) | 138/140 (99%, CI 95–100) | 0.706 | 20.8 | 2.3 |
| mistral-7b/modelfile | 92/100 (92%, CI 85–96) | 2/100 | 21/40 (52%, CI 37–67) | 138/140 (99%, CI 95–100) | 0.711 | 20.7 | 2.2 |

## So sánh cặp trên cùng câu hỏi (hiệu = A − B; khoảng tin cậy 95% bootstrap ghép cặp; nếu khoảng chứa 0 thì KHÔNG khác biệt có ý nghĩa)

| A so với B | Δ đúng (có đáp án) | Δ từ chối đúng (ngoài tài liệu) | Δ đúng ngôn ngữ |
|---|---|---|---|
| qwen2.5-7b/modelfile vs qwen2.5-7b/base | +1.0 điểm % [-3.0, +5.0] | +2.5 điểm % [-10.0, +15.0] | +10.0 điểm % [+5.0, +15.0] ★ |
| qwen2.5-7b/modelfile vs qwen2.5-7b/base+rules | +0.0 điểm % [-3.0, +3.0] | -5.0 điểm % [-12.5, +0.0] | +0.7 điểm % [+0.0, +2.1] |
| qwen2.5-7b/base+rules vs qwen2.5-7b/base | +1.0 điểm % [-3.0, +6.0] | +7.5 điểm % [-5.0, +20.0] | +9.3 điểm % [+5.0, +14.3] ★ |
| llama3.1-8b/modelfile vs llama3.1-8b/base | -1.0 điểm % [-7.0, +5.0] | -15.0 điểm % [-27.5, -2.5] ★ | +9.3 điểm % [+5.0, +14.3] ★ |
| llama3.1-8b/modelfile vs llama3.1-8b/base+rules | -3.0 điểm % [-7.0, +0.0] | -2.5 điểm % [-15.0, +7.5] | +0.0 điểm % [+0.0, +0.0] |
| llama3.1-8b/base+rules vs llama3.1-8b/base | +2.0 điểm % [-3.0, +7.0] | -12.5 điểm % [-25.0, +0.0] | +9.3 điểm % [+5.0, +14.3] ★ |
| mistral-7b/modelfile vs mistral-7b/base | +10.0 điểm % [+3.0, +18.0] ★ | -27.5 điểm % [-45.0, -10.0] ★ | +23.6 điểm % [+16.4, +30.7] ★ |
| mistral-7b/modelfile vs mistral-7b/base+rules | +1.0 điểm % [+0.0, +3.0] | +0.0 điểm % [-7.5, +7.5] | +0.0 điểm % [-2.1, +2.1] |
| mistral-7b/base+rules vs mistral-7b/base | +9.0 điểm % [+1.0, +17.0] ★ | -27.5 điểm % [-45.0, -10.0] ★ | +23.6 điểm % [+16.4, +30.7] ★ |

★ = khác biệt có ý nghĩa thống kê (khoảng tin cậy không chứa 0).
\* Bám tài liệu = tỉ lệ từ nội dung (>=5 ký tự) của câu trả lời có mặt trong đoạn trích — chỉ là chỉ số gần đúng.
Đúng = có đáp án: không từ chối và khớp nhóm từ khóa; ngoài tài liệu: từ chối. Chỉ số từ khóa khá cứng nên có thể chấm sai một số câu trả lời đúng.
