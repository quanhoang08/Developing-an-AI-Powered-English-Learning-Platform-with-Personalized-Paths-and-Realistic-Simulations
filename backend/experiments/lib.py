# Thư viện dùng chung cho các thực nghiệm RAG: nạp dữ liệu, BM25, embedding bge-m3 (có cache đĩa),
# gộp xếp hạng RRF và các thước đo retrieval. Không đụng DB hay ứng dụng — chỉ cần Ollama chạy local.
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))  # để import app.utils.chunking khi chạy như script

CORPUS_DIR = ROOT / "corpus"
RESULTS_DIR = ROOT / "results"
QA_PATH = ROOT / "qa_set.json"
RESULTS_DIR.mkdir(exist_ok=True)


CORPUS_TEST_DIR = ROOT / "corpus_test"  # bộ GIỮ KÍN: chưa từng dùng để chỉnh Modelfile/prompt
QA_TEST_PATH = ROOT / "qa_test.json"


def load_docs(directory: Path = CORPUS_DIR) -> dict[str, str]:
	return {path.name: path.read_text(encoding="utf-8") for path in sorted(directory.glob("*.txt"))}


def load_qa(path: Path = QA_PATH) -> list[dict]:
	return json.loads(path.read_text(encoding="utf-8"))


def normalize(text: str) -> str:
	return re.sub(r"\s+", " ", text.lower()).strip()


def tokenize(text: str) -> list[str]:
	# \w hiểu Unicode nên tiếng Việt có dấu được giữ nguyên; mỗi âm tiết là 1 token.
	return re.findall(r"\w+", text.lower())


# ---------- BM25 (lexical) ----------

class BM25:
	def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75) -> None:
		self.k1, self.b = k1, b
		self.tokens = [tokenize(d) for d in documents]
		self.lengths = [len(t) for t in self.tokens]
		self.avg_length = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
		self.term_freqs = [Counter(t) for t in self.tokens]
		document_freq: Counter = Counter()
		for tokens in self.tokens:
			document_freq.update(set(tokens))
		total = len(documents)
		self.idf = {
			term: math.log(1 + (total - freq + 0.5) / (freq + 0.5)) for term, freq in document_freq.items()
		}

	def scores(self, query: str) -> list[float]:
		query_terms = tokenize(query)
		result = []
		for freqs, length in zip(self.term_freqs, self.lengths):
			score = 0.0
			for term in query_terms:
				frequency = freqs.get(term, 0)
				if not frequency:
					continue
				norm = 1 - self.b + self.b * length / (self.avg_length or 1)
				score += self.idf.get(term, 0.0) * frequency * (self.k1 + 1) / (frequency + self.k1 * norm)
			result.append(score)
		return result


# ---------- Embedding qua Ollama (có cache đĩa để chạy lại không tốn thời gian) ----------

EMBED_CACHE_PATH = RESULTS_DIR / "embed_cache.json"
_embed_cache: dict[str, list[float]] | None = None


def _load_cache() -> dict[str, list[float]]:
	global _embed_cache
	if _embed_cache is None:
		_embed_cache = json.loads(EMBED_CACHE_PATH.read_text()) if EMBED_CACHE_PATH.exists() else {}
	return _embed_cache


def embed(texts: list[str], model: str = "bge-m3") -> list[list[float]]:
	import ollama

	cache = _load_cache()
	keys = [hashlib.sha1(f"{model}\x1f{text}".encode()).hexdigest() for text in texts]
	missing = [(key, text) for key, text in zip(keys, texts) if key not in cache]
	if missing:
		client = ollama.Client()
		for start in range(0, len(missing), 16):
			batch = missing[start : start + 16]
			response = client.embed(model=model, input=[text for _, text in batch])
			for (key, _), vector in zip(batch, response.embeddings):
				cache[key] = vector
		EMBED_CACHE_PATH.write_text(json.dumps(cache))
	return [cache[key] for key in keys]


def cosine_scores(query_vector: list[float], vectors: list[list[float]]) -> list[float]:
	query_norm = math.sqrt(sum(x * x for x in query_vector)) or 1.0
	scores = []
	for vector in vectors:
		norm = math.sqrt(sum(x * x for x in vector)) or 1.0
		scores.append(sum(a * b for a, b in zip(query_vector, vector)) / (query_norm * norm))
	return scores


def rank_by(scores: list[float]) -> list[int]:
	return sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = 60) -> list[int]:
	"""Gộp nhiều bảng xếp hạng (vd. BM25 + dense) bằng RRF — không cần chuẩn hóa điểm giữa các hệ thống."""
	fused: dict[int, float] = {}
	for ranking in rankings:
		for position, index in enumerate(ranking):
			fused[index] = fused.get(index, 0.0) + 1.0 / (k + position + 1)
	return sorted(fused, key=lambda index: fused[index], reverse=True)


# ---------- Thước đo retrieval ----------

def gold_rank(ranked_chunks: list[str], evidence: str) -> int | None:
	"""Vị trí (từ 1) của chunk đầu tiên chứa nguyên văn đoạn bằng chứng; None nếu không chunk nào chứa."""
	target = normalize(evidence)
	for position, chunk in enumerate(ranked_chunks, start=1):
		if target in normalize(chunk):
			return position
	return None


def summarize(ranks: list[int | None], k_values: tuple[int, ...] = (1, 3, 5)) -> dict[str, float]:
	total = len(ranks) or 1
	summary = {f"hit@{k}": sum(1 for r in ranks if r is not None and r <= k) / total for k in k_values}
	summary["mrr@5"] = sum(1 / r for r in ranks if r is not None and r <= 5) / total
	return summary
