# Thực nghiệm 1 — Tối ưu pipeline RAG: chiến lược chunking × cỡ chunk × bộ truy hồi (BM25 / dense bge-m3 / hybrid RRF)
# trên tài liệu Anh, Việt và song ngữ. Chỉ cần Ollama có model bge-m3 (`ollama pull bge-m3`).
# Chạy:  python experiments/run_retrieval.py     → results/retrieval.json + results/retrieval.md
import json
import time

import lib
from app.utils.chunking import chunk_document

# (nhãn, chiến lược, overlap_sentences)
STRATEGIES = [
	("fixed", "fixed", 0),
	("paragraph", "paragraph", 0),
	("sentence-o0", "sentence", 0),
	("sentence-o1", "sentence", 1),
]
CHUNK_SIZES = [60, 120, 200]
RETRIEVERS = ["bm25", "dense", "hybrid"]
DOC_LANG = {"en_spaced_repetition.txt": "en", "vi_present_perfect.txt": "vi", "bilingual_phrasal_verbs.txt": "mixed"}


def question_kind(question: dict) -> str:
	doc_lang = DOC_LANG[question["doc"]]
	if doc_lang == "mixed":
		return "bilingual-doc"
	return "same-language" if doc_lang == question["lang"] else "cross-language"


def main() -> None:
	docs = lib.load_docs()
	questions = [q for q in lib.load_qa() if q["answerable"]]
	rows = []
	started = time.time()

	for label, strategy, overlap in STRATEGIES:
		for size in CHUNK_SIZES:
			chunked = {name: chunk_document(text, strategy, size, overlap) for name, text in docs.items()}
			chunk_vectors = {name: lib.embed(chunks) for name, chunks in chunked.items()}
			bm25 = {name: lib.BM25(chunks) for name, chunks in chunked.items()}
			query_vectors = lib.embed([q["question"] for q in questions])
			all_chunks = [c for chunks in chunked.values() for c in chunks]
			# Giới hạn trên: câu hỏi mà bằng chứng bị cắt đôi giữa 2 chunk thì không retriever nào cứu được.
			coverage = sum(1 for q in questions if lib.gold_rank(chunked[q["doc"]], q["evidence"])) / len(questions)

			per_retriever: dict[str, list[tuple[dict, int | None]]] = {r: [] for r in RETRIEVERS}
			for question, query_vector in zip(questions, query_vectors):
				name = question["doc"]
				chunks = chunked[name]
				lexical = lib.rank_by(bm25[name].scores(question["question"]))
				dense = lib.rank_by(lib.cosine_scores(query_vector, chunk_vectors[name]))
				orderings = {"bm25": lexical, "dense": dense, "hybrid": lib.reciprocal_rank_fusion([lexical, dense])}
				for retriever, order in orderings.items():
					rank = lib.gold_rank([chunks[i] for i in order[:5]], question["evidence"])
					per_retriever[retriever].append((question, rank))

			for retriever, results in per_retriever.items():
				row = {
					"chunking": label, "chunk_words": size, "retriever": retriever,
					"n_chunks": len(all_chunks),
					"avg_chunk_words": round(sum(len(c.split()) for c in all_chunks) / len(all_chunks), 1),
					"evidence_coverage": round(coverage, 3),
					**{k: round(v, 3) for k, v in lib.summarize([r for _, r in results]).items()},
				}
				for kind in ("same-language", "cross-language", "bilingual-doc"):
					subset = [r for q, r in results if question_kind(q) == kind]
					row[f"mrr@5[{kind}]"] = round(lib.summarize(subset)["mrr@5"], 3) if subset else None
				rows.append(row)
			print(f"{label:12s} size={size:3d} done ({time.time() - started:.0f}s)", flush=True)

	(lib.RESULTS_DIR / "retrieval.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
	(lib.RESULTS_DIR / "retrieval.md").write_text(render_markdown(rows, len(questions)), encoding="utf-8")
	print("wrote results/retrieval.json and results/retrieval.md")


def render_markdown(rows: list[dict], n_questions: int) -> str:
	ordered = sorted(rows, key=lambda r: (r["mrr@5"], r["hit@1"]), reverse=True)
	lines = [
		f"# Kết quả thực nghiệm retrieval ({n_questions} câu hỏi có đáp án, embedding bge-m3)", "",
		"| Chunking | Từ/chunk | Retriever | #chunk | Coverage | hit@1 | hit@3 | hit@5 | MRR@5 | MRR cùng ngôn ngữ | MRR khác ngôn ngữ | MRR tài liệu song ngữ |",
		"|---|---|---|---|---|---|---|---|---|---|---|---|",
	]
	for r in ordered:
		lines.append(
			f"| {r['chunking']} | {r['chunk_words']} | {r['retriever']} | {r['n_chunks']} | {r['evidence_coverage']} | "
			f"{r['hit@1']} | {r['hit@3']} | {r['hit@5']} | **{r['mrr@5']}** | {r['mrr@5[same-language]']} | "
			f"{r['mrr@5[cross-language]']} | {r['mrr@5[bilingual-doc]']} |"
		)
	lines += ["", "Coverage = tỉ lệ câu hỏi có nguyên đoạn bằng chứng nằm trọn trong ít nhất 1 chunk (giới hạn trên của mọi retriever)."]
	return "\n".join(lines) + "\n"


if __name__ == "__main__":
	main()
