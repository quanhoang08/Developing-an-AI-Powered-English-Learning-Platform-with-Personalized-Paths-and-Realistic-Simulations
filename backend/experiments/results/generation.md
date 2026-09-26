# Kết quả thực nghiệm sinh câu trả lời (RAG: sentence-o1/120 từ + bge-m3, top-3)

| Biến thể | Đúng (có đáp án) | Từ chối nhầm | Từ chối đúng (không có đáp án) | Bịa đáp án | Đúng ngôn ngữ | Bám tài liệu* | Số từ TB | Giây/câu | Token/giây |
|---|---|---|---|---|---|---|---|---|---|
| qwen2.5-7b/base | 23/24 | 1/24 | 7/7 | 0/7 | 26/31 | 0.834 | 19.6 | 3.8 | 27.0 |
| qwen2.5-7b/modelfile | 22/24 | 0/24 | 6/7 | 1/7 | 30/31 | 0.745 | 19.2 | 1.6 | 27.8 |
| llama3.1-8b/base | 23/24 | 1/24 | 7/7 | 0/7 | 29/31 | 0.843 | 16.3 | 3.0 | 21.3 |
| llama3.1-8b/modelfile | 22/24 | 0/24 | 6/7 | 1/7 | 31/31 | 0.722 | 15.4 | 1.6 | 22.6 |
| mistral-7b/base | 23/24 | 0/24 | 6/7 | 1/7 | 22/31 | 0.59 | 32.3 | 2.9 | 25.3 |
| mistral-7b/modelfile | 23/24 | 0/24 | 3/7 | 4/7 | 31/31 | 0.751 | 27.7 | 3.0 | 24.8 |

\* Bám tài liệu = tỉ lệ từ nội dung (>=5 ký tự) trong câu trả lời có mặt trong đoạn trích được truy hồi — chỉ là chỉ số gần đúng, không thay cho đánh giá của người.
Từ chối = câu trả lời nói rõ tài liệu không đề cập; Bịa đáp án = câu hỏi NGOÀI tài liệu mà model vẫn trả lời.
