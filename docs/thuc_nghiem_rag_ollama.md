# Thực nghiệm RAG chạy local với Ollama — đáp ứng góp ý của giảng viên hướng dẫn

Tài liệu này ghi lại những gì đã làm để đáp ứng 4 góp ý của giảng viên, cách tái lập thực nghiệm, số liệu thật thu được và các hạn chế cần nêu trung thực trong báo cáo.

## 1. Đối chiếu với 4 góp ý

| # | Góp ý của giảng viên | Hiện trạng trước khi bổ sung | Đã bổ sung |
|---|---|---|---|
| 1 | Chạy Ollama ở local với các model có sẵn (Llama 3, Mistral, Qwen) | Có client Ollama và Qwen 7B, nhưng **embedding vẫn gọi Gemini (cloud)** và chat mặc định Gemini | Chat RAG mặc định `LLM_PROVIDER=ollama`; embedding chuyển sang **bge-m3 local**; đã tải và thử cả Llama 3.1 8B, Mistral 7B, Qwen 2.5 7B |
| 2 | Tùy biến model qua Modelfile để AI bám tài liệu, không lan man | Không có Modelfile; luật trả lời nằm trong prompt | `backend/modelfiles/create_models.py` sinh 3 Modelfile (`lumina-rag-*`): SYSTEM prompt, tham số cố định, few-shot; app dùng model này và tự lùi về model gốc nếu chưa tạo |
| 3 | Chạy thực nghiệm so sánh các mô hình | Không có | `backend/experiments/` gồm bộ dữ liệu 31 câu hỏi và 2 script thực nghiệm, kết quả trong `experiments/results/` |
| 4 | Tối ưu pipeline RAG: chunking, chọn model cho tài liệu song ngữ | Chỉ có cắt cứng 350 từ | Bộ chunking 3 chiến lược (`app/utils/chunking.py`), so sánh chunking × cỡ chunk × retriever, chọn embedding đa ngữ bge-m3 |

## 2. Thiết lập thực nghiệm

- **Phần cứng:** RTX 4050 Laptop (6 GB VRAM), 16 CPU. Mọi model ở dạng quantized 4-bit qua Ollama.
- **Corpus** (`experiments/corpus/`, ~500 từ/tài liệu): tài liệu tiếng Anh (spaced repetition), tiếng Việt (thì hiện tại hoàn thành) và song ngữ Anh–Việt (phrasal verbs).
- **Bộ câu hỏi** (`experiments/qa_set.json`): 31 câu, gồm 24 câu có đáp án trong tài liệu (có cả câu hỏi khác ngôn ngữ với tài liệu) và 7 câu **không có** trong tài liệu để đo việc bịa đáp án. Mỗi câu có đoạn bằng chứng nguyên văn và nhóm từ khóa đáp án.
- **Tái lập:**

```bash
ollama pull bge-m3 && ollama pull llama3.1:8b && ollama pull mistral:7b
python modelfiles/create_models.py          # tạo lumina-rag-qwen / -llama / -mistral
python experiments/run_retrieval.py         # → experiments/results/retrieval.md
python experiments/run_generation.py        # → experiments/results/generation.md
```

## 3. Thực nghiệm 1 — Chunking và truy hồi (24 câu, embedding bge-m3)

Chia chunk: `fixed` (cắt cứng theo số từ, baseline cũ), `paragraph` (gom nguyên đoạn), `sentence` (gom nguyên câu, có/không chồng lấp 1 câu). Retriever: BM25, dense (bge-m3), hybrid (RRF). Bảng đầy đủ 36 cấu hình: `experiments/results/retrieval.md`.

| Cấu hình | Coverage | hit@1 | MRR@5 | MRR khác ngôn ngữ |
|---|---|---|---|---|
| paragraph, 120 từ, dense | 1.00 | 0.875 | 0.924 | 1.00 |
| sentence + overlap 1, 120 từ, dense (**đang dùng**) | 1.00 | 0.833 | 0.892 | 0.84 |
| fixed, 200 từ, dense | 1.00 | 0.792 | 0.896 | 0.90 |
| fixed, 60 từ, dense | 0.875 | 0.708 | 0.753 | 0.60 |
| fixed, 120 từ, BM25 | 0.917 | 0.708 | 0.802 | 0.55 |

*Coverage = tỉ lệ câu hỏi có nguyên đoạn bằng chứng nằm trọn trong ít nhất 1 chunk.*

**Phát hiện đáng tin (không phải nhiễu):**
1. Cắt cứng theo số từ làm **mất bằng chứng** (coverage 0.875 ở 60 từ, 0.917 ở 120 từ); chia theo câu giữ coverage = 1.0 ở mọi cỡ.
2. Chunk 60 từ kém rõ rệt so với 120–200 từ ở mọi chiến lược.
3. Với câu hỏi **khác ngôn ngữ** với tài liệu, dense đa ngữ vượt xa BM25 (MRR 0.60–1.00 so với 0.40–0.67 của BM25; ở các cỡ chunk từ 120 từ trở lên dense đạt 0.65–1.00), vì từ khóa không trùng giữa hai ngôn ngữ. Hybrid **không** cải thiện tổng thể so với dense thuần trên bộ này, nên hệ thống giữ dense.

**Quyết định:** chia theo câu, ~120 từ, chồng lấp 1 câu, truy hồi dense bằng bge-m3. Cấu hình paragraph-120 nhỉnh hơn 0.03 MRR nhưng chênh lệch này bằng chưa tới 1 câu hỏi; sentence được chọn vì không phụ thuộc cấu trúc đoạn văn của tài liệu (đoạn quá dài buộc phải cắt cứng).

## 4. Thực nghiệm 2 — So sánh model và hiệu quả của Modelfile (31 câu)

Toàn bộ chạy qua pipeline RAG đề xuất (top-3 chunk). Với mỗi model so sánh **base** (model gốc + prompt RAG hiện tại của dự án, temperature 0.7) và **modelfile** (model `lumina-rag-*`). Số liệu cuối (Modelfile v3):

| Biến thể | Đúng (24) | Từ chối nhầm | Bịa đáp án (7) | Đúng ngôn ngữ (31) | Giây/câu |
|---|---|---|---|---|---|
| qwen2.5-7b / base | 23 | 1 | 0 | 26 | 3.8 |
| **qwen2.5-7b / modelfile** | 22 | 0 | 1 | 30 | **1.6** |
| llama3.1-8b / base | 23 | 1 | 0 | 29 | 3.0 |
| llama3.1-8b / modelfile | 22 | 0 | 1 | 31 | 1.6 |
| mistral-7b / base | 23 | 0 | 1 | 22 | 2.9 |
| mistral-7b / modelfile | 23 | 0 | **4** | 31 | 3.0 |

### Modelfile được cải tiến qua 3 vòng (ghi lại để báo cáo trung thực)

| Phiên bản | Thay đổi | Kết quả chính |
|---|---|---|
| v1 | SYSTEM prompt với câu từ chối song ngữ gộp một câu | **Kém hơn base**: Qwen trả lời tiếng Việt cho câu hỏi tiếng Anh (đúng ngôn ngữ 19/31), Llama từ chối nhầm 3 câu, Mistral bịa 3/7 |
| v2 | Tách câu từ chối theo ngôn ngữ, thêm few-shot (chủ đề khác corpus) | Qwen đúng 24/24, không từ chối nhầm, nhưng vẫn trôi ngôn ngữ (23/31) |
| v3 | Hệ thống tự phát hiện ngôn ngữ câu hỏi (`app/utils/language.py`) và ghi dòng `ANSWER LANGUAGE` vào prompt | Đúng ngôn ngữ 30–31/31 ở cả ba model |

**Kết luận thực nghiệm 2:**
- Modelfile giúp **nhanh hơn ~2 lần** (câu trả lời ngắn, tham số cố định), **không từ chối nhầm**, và với hệ thống chọn ngôn ngữ đích thì trả lời **đúng ngôn ngữ hơn** model gốc.
- Model 7B **không tự tuân thủ luật ngôn ngữ** dù có SYSTEM prompt; cần ép bằng logic ngoài model. Đây là phát hiện đáng đưa vào báo cáo.
- **Mistral 7B không phù hợp** cho bài toán "chỉ trả lời theo tài liệu": bịa 4/7 câu ngoài tài liệu dù có Modelfile.
- Qwen và Llama tương đương về chất lượng; chọn **Qwen 2.5** làm mặc định vì nhanh nhất, dùng chung model với các tính năng khác nên không phải nạp/đổi model trong 6 GB VRAM.
- Với Modelfile, số liệu "độ bám tài liệu" (0.72–0.75) thấp hơn base (0.83–0.84). Chỉ số này là **xấp xỉ theo từ vựng**: model Modelfile diễn đạt lại và trích dẫn `[1]` nên ít sao chép nguyên văn hơn, chưa chắc là kém trung thực hơn. Cần đánh giá bởi người để kết luận.

## 5. Hạn chế (cần nêu trong báo cáo)

- **Quy mô nhỏ:** 24 + 7 câu hỏi, 3 tài liệu ~500 từ. Mỗi câu = 0.04 hit@1, nên chênh lệch dưới ~0.05 là nằm trong nhiễu. Nên mở rộng bằng tài liệu thật của người dùng.
- **Tinh chỉnh trên chính bộ đánh giá:** Modelfile được chỉnh qua 3 vòng dựa trên kết quả của cùng 31 câu. Few-shot dùng chủ đề khác corpus để tránh rò dữ liệu, nhưng vẫn có nguy cơ overfit; cần bộ kiểm tra riêng.
- **Chỉ số tự động thô:** đúng/sai chấm bằng từ khóa (có trường hợp trả lời đúng nhưng dùng từ khác bị tính sai), độ bám tài liệu chỉ là xấp xỉ, nhận diện ngôn ngữ bằng ký tự có dấu (câu hỏi tiếng Việt không dấu sẽ bị coi là tiếng Anh). Chưa có đánh giá bằng người hoặc LLM-as-judge.
- **Chưa so sánh với embedding Gemini** (cloud, bị giới hạn quota) nên chưa kết luận bge-m3 tốt hơn Gemini, chỉ kết luận bge-m3 đạt chất lượng tốt, chạy local và đa ngữ. Chưa thử `paraphrase-multilingual` và `nomic-embed-text`.
- Chỉ đo với model 7–8B quantized trên GPU 6 GB; kết quả tốc độ phụ thuộc phần cứng.

## 6. Thay đổi trong hệ thống

- `app/utils/chunking.py`: 3 chiến lược chunking, tách câu nhận biết tiếng Việt; cấu hình `CHUNK_STRATEGY`, `CHUNK_MAX_WORDS`, `CHUNK_OVERLAP_SENTENCES`.
- `EMBEDDING_PROVIDER=ollama` (bge-m3, 1024 chiều) ghi vào cột mới `document_chunks.embedding_local` (migration `20260919_0011`, chỉ thêm cột, không xóa dữ liệu Gemini cũ). Chunk có sẵn được embed lại bằng `python scripts/reindex_embeddings.py`. Đặt `EMBEDDING_PROVIDER=gemini` để quay lại.
- `llm_service.answer_grounded_question`: mặc định theo `LLM_PROVIDER` (Ollama) và dùng model `OLLAMA_RAG_MODEL_NAME`; nếu chưa tạo Modelfile thì tự lùi về model gốc.
- Test: `tests/test_chunking.py`, `tests/test_rag_local_pipeline.py`.
