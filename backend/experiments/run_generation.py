# Thực nghiệm 2 — So sánh các mô hình chạy local (Qwen2.5 / Llama 3.1 / Mistral) và hiệu quả của Modelfile.
# Mỗi câu hỏi chạy qua ĐÚNG pipeline RAG đề xuất (chunk theo câu, overlap 1, 120 từ; truy hồi dense bge-m3, top-3),
# rồi sinh câu trả lời bằng 3 kiểu:
#   base       — model gốc + prompt RAG hiện tại của dự án (rules trong user prompt, temperature 0.7)
#   base+rules — ĐỐI CHỨNG: model gốc nhưng được đưa đúng SYSTEM prompt + few-shot + tham số của Modelfile qua API.
#                So với modelfile cho biết lợi ích đến từ "đóng gói Modelfile" hay chỉ từ nội dung prompt.
#   modelfile  — model tùy biến lumina-rag-* (SYSTEM + few-shot + tham số nằm trong Modelfile)
# Hai bộ dữ liệu:
#   dev  — qa_set.json, corpus/         : bộ đã dùng để chỉnh Modelfile (dễ bị lạc quan)
#   test — qa_test.json, corpus_test/   : bộ GIỮ KÍN, chưa từng dùng để chỉnh; dùng để báo cáo chính thức
# Chạy:  python experiments/run_generation.py [--set dev|test] [--report]
#        (tiếp tục được nếu bị ngắt; --report chỉ tính lại bảng từ kết quả đã có)
import json
import random
import re
import sys
import time
import unicodedata
from math import sqrt

import lib
import ollama
from app.utils.chunking import chunk_document
from app.utils.language import language_name
from modelfiles.create_models import FEW_SHOT, PARAMETERS, SYSTEM_PROMPT

CHUNK_STRATEGY, CHUNK_WORDS, OVERLAP, TOP_K = "sentence", 120, 1, 3
VARIANTS = [  # (nhãn, model Ollama, kiểu prompt)
	("qwen2.5-7b/base", "qwen2.5:7b-instruct-q4_K_M", "plain"),
	("qwen2.5-7b/base+rules", "qwen2.5:7b-instruct-q4_K_M", "rules"),
	("qwen2.5-7b/modelfile", "lumina-rag-qwen", "modelfile"),
	("llama3.1-8b/base", "llama3.1:8b", "plain"),
	("llama3.1-8b/base+rules", "llama3.1:8b", "rules"),
	("llama3.1-8b/modelfile", "lumina-rag-llama", "modelfile"),
	("mistral-7b/base", "mistral:7b", "plain"),
	("mistral-7b/base+rules", "mistral:7b", "rules"),
	("mistral-7b/modelfile", "lumina-rag-mistral", "modelfile"),
]
# (thư mục tài liệu, file câu hỏi, hậu tố file kết quả)
SETS = {
	"dev": (lib.CORPUS_DIR, lib.QA_PATH, ""),
	"test": (lib.CORPUS_TEST_DIR, lib.QA_TEST_PATH, "_test"),
}

# Prompt RAG hiện tại của dự án (llm_service.answer_grounded_question) — làm đường cơ sở "trước khi tùy biến".
PLAIN_PROMPT = """You are a helpful study assistant answering questions about a document the
student uploaded. Answer ONLY using the excerpts below. If the excerpts don't contain the
answer, say clearly that the document doesn't cover it -- do NOT use outside knowledge.

DOCUMENT EXCERPTS:
\"\"\"{context}\"\"\"

CONVERSATION SO FAR:
(no previous turns)

STUDENT QUESTION: {question}

Answer concisely and directly."""

REFUSAL_PATTERN = re.compile(
	r"không đề cập|không có (?:thông tin|trong tài liệu)|không nói|không được nhắc|"
	r"do(?:es)? not (?:cover|mention|contain|provide|include|address|discuss)|"
	r"do(?:es)?n't (?:cover|mention|contain|provide|include|address|discuss)|"
	r"not covered|cannot find|can't find|not (?:mentioned|found|included|discussed) in|no information|"
	r"không thấy|không tìm thấy|không (?:có|nêu|cung cấp) (?:nội dung|thông tin)",
	re.IGNORECASE,
)
_VI_CHARS = set("ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ")


def fold(text: str) -> str:
	"""Chữ thường, bỏ dấu — so khớp từ khóa không bị lệch vì gõ dấu khác nhau."""
	decomposed = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
	return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def is_refusal(answer: str) -> bool:
	return bool(REFUSAL_PATTERN.search(answer))


def keywords_ok(answer: str, groups: list[list[str]]) -> bool:
	folded = fold(answer)
	return all(any(fold(option) in folded for option in group) for group in groups)


def answer_language(answer: str) -> str:
	letters = [ch for ch in answer.lower() if ch.isalpha()]
	vietnamese = sum(1 for ch in letters if ch in _VI_CHARS)
	return "vi" if letters and vietnamese / len(letters) > 0.02 else "en"


def grounded_ratio(answer: str, context: str) -> float:
	"""Proxy độ bám tài liệu: tỉ lệ từ nội dung (>=5 ký tự) của câu trả lời xuất hiện trong ngữ cảnh."""
	context_tokens = set(re.findall(r"\w+", fold(context)))
	answer_tokens = [t for t in re.findall(r"\w+", fold(answer)) if len(t) >= 5]
	return sum(1 for t in answer_tokens if t in context_tokens) / len(answer_tokens) if answer_tokens else 1.0


def record_ok(record: dict, question: dict) -> bool:
	"""Có đáp án: đúng nếu không từ chối và khớp từ khóa. Không có đáp án: đúng nếu từ chối."""
	refused = is_refusal(record["answer"])
	if question["answerable"]:
		return not refused and keywords_ok(record["answer"], question["keywords"])
	return refused


# ---------- thống kê ----------

def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
	"""Khoảng tin cậy Wilson 95% cho 1 tỉ lệ — đúng cả khi tỉ lệ gần 0 hoặc 1 và mẫu nhỏ."""
	if total == 0:
		return 0.0, 0.0
	p = successes / total
	denom = 1 + z * z / total
	centre = (p + z * z / (2 * total)) / denom
	half = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
	return max(0.0, centre - half), min(1.0, centre + half)


def paired_bootstrap(a: list[int], b: list[int], rounds: int = 4000) -> tuple[float, float, float]:
	"""Chênh lệch trung bình (a − b) trên CÙNG các câu hỏi + khoảng tin cậy 95% bằng bootstrap ghép cặp."""
	rng = random.Random(0)
	n = len(a)
	diffs = [x - y for x, y in zip(a, b)]
	means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(rounds))
	return sum(diffs) / n, means[int(0.025 * rounds)], means[int(0.975 * rounds) - 1]


def fmt_ci(successes: int, total: int) -> str:
	low, high = wilson(successes, total)
	return f"{successes}/{total} ({100 * successes / total:.0f}%, CI {100 * low:.0f}–{100 * high:.0f})"


# ---------- chạy thực nghiệm ----------

def build_retrievers(docs: dict[str, str]):
	chunked = {n: chunk_document(t, CHUNK_STRATEGY, CHUNK_WORDS, OVERLAP) for n, t in docs.items()}
	vectors = {n: lib.embed(c) for n, c in chunked.items()}

	def retrieve(doc: str, question: str) -> list[str]:
		scores = lib.cosine_scores(lib.embed([question])[0], vectors[doc])
		return [chunked[doc][i] for i in lib.rank_by(scores)[:TOP_K]]

	return retrieve


def user_prompt(chunks: list[str], question: str) -> str:
	excerpts = "\n\n".join(f"[{i}] {chunk}" for i, chunk in enumerate(chunks, start=1))
	return f"EXCERPTS:\n{excerpts}\n\nQUESTION: {question}\nANSWER LANGUAGE: {language_name(question)}"


def generate(client: ollama.Client, model: str, style: str, chunks: list[str], question: str) -> dict:
	if style == "plain":
		messages = [{"role": "user", "content": PLAIN_PROMPT.format(context="\n\n---\n\n".join(chunks), question=question)}]
		options = {"temperature": 0.7, "seed": 42, "num_predict": 600}  # temperature = mặc định OLLAMA_TEMPERATURE của dự án
	elif style == "rules":
		# Cùng nội dung như Modelfile nhưng truyền qua API trên model gốc (đối chứng cho phần "đóng gói").
		messages = [{"role": "system", "content": SYSTEM_PROMPT}]
		for excerpt, shot_question, answer in FEW_SHOT:
			messages.append({"role": "user", "content": f"EXCERPTS:\n{excerpt}\n\nQUESTION: {shot_question}\nANSWER LANGUAGE: {language_name(shot_question)}"})
			messages.append({"role": "assistant", "content": answer})
		messages.append({"role": "user", "content": user_prompt(chunks, question)})
		options = {**PARAMETERS, "seed": 42}
	else:
		messages = [{"role": "user", "content": user_prompt(chunks, question)}]
		options = {"seed": 42}  # còn lại lấy từ PARAMETER trong Modelfile
	started = time.time()
	response = client.chat(model=model, messages=messages, options=options)
	elapsed = time.time() - started
	tokens = response.eval_count or 0
	eval_seconds = (response.eval_duration or 0) / 1e9
	return {
		"answer": response.message.content.strip(),
		"latency_s": round(elapsed, 1),
		"tokens": tokens,
		"tokens_per_s": round(tokens / eval_seconds, 1) if eval_seconds else None,
	}


def run(set_name: str) -> None:
	docs_dir, qa_path, suffix = SETS[set_name]
	results_path = lib.RESULTS_DIR / f"generation{suffix}.jsonl"
	docs, questions = lib.load_docs(docs_dir), lib.load_qa(qa_path)
	retrieve = build_retrievers(docs)
	done = set()
	if results_path.exists():
		for line in results_path.read_text(encoding="utf-8").splitlines():
			record = json.loads(line)
			done.add((record["variant"], record["id"]))
	client = ollama.Client(timeout=300)
	for label, model, style in VARIANTS:
		for question in questions:
			if (label, question["id"]) in done:
				continue
			chunks = retrieve(question["doc"], question["question"])
			record = {"variant": label, "id": question["id"], "context": chunks, **generate(client, model, style, chunks, question["question"])}
			with results_path.open("a", encoding="utf-8") as handle:
				handle.write(json.dumps(record, ensure_ascii=False) + "\n")
			print(f"{label:26s} {question['id']} {record['latency_s']:>5}s", flush=True)


def report(set_name: str) -> None:
	docs_dir, qa_path, suffix = SETS[set_name]
	questions = {q["id"]: q for q in lib.load_qa(qa_path)}
	records = [json.loads(line) for line in (lib.RESULTS_DIR / f"generation{suffix}.jsonl").read_text(encoding="utf-8").splitlines()]
	n_answerable = sum(q["answerable"] for q in questions.values())
	n_unanswerable = len(questions) - n_answerable
	lines = [
		f"# Kết quả sinh câu trả lời — bộ {'GIỮ KÍN (test)' if set_name == 'test' else 'phát triển (dev)'}: {n_answerable} câu có đáp án + {n_unanswerable} câu ngoài tài liệu",
		"", "Pipeline RAG: sentence-o1/120 từ + bge-m3, top-3. Trong ngoặc là % và khoảng tin cậy Wilson 95%.", "",
		"| Biến thể | Đúng (có đáp án) | Từ chối nhầm | Từ chối đúng (ngoài tài liệu) | Đúng ngôn ngữ | Bám tài liệu* | Số từ TB | Giây/câu |",
		"|---|---|---|---|---|---|---|---|",
	]
	summary, flags = [], {}
	for label, _, _ in VARIANTS:
		rows = {r["id"]: r for r in records if r["variant"] == label}
		if len(rows) < len(questions):
			continue
		answerable = [r for i, r in rows.items() if questions[i]["answerable"]]
		unanswerable = [r for i, r in rows.items() if not questions[i]["answerable"]]
		correct = sum(record_ok(r, questions[r["id"]]) for r in answerable)
		false_refusal = sum(is_refusal(r["answer"]) for r in answerable)
		refused = sum(is_refusal(r["answer"]) for r in unanswerable)
		lang_ok = sum(is_refusal(r["answer"]) or answer_language(r["answer"]) == questions[r["id"]]["lang"] for r in rows.values())
		grounded = [grounded_ratio(r["answer"], "\n".join(r["context"])) for r in rows.values() if not is_refusal(r["answer"])]
		flags[label] = {
			"correct": [int(record_ok(rows[i], questions[i])) for i in sorted(rows) if questions[i]["answerable"]],
			"refused": [int(record_ok(rows[i], questions[i])) for i in sorted(rows) if not questions[i]["answerable"]],
			"lang": [int(is_refusal(rows[i]["answer"]) or answer_language(rows[i]["answer"]) == questions[i]["lang"]) for i in sorted(rows)],
		}
		entry = {
			"variant": label, "correct": correct, "n_answerable": len(answerable), "false_refusal": false_refusal,
			"refused_unanswerable": refused, "n_unanswerable": len(unanswerable), "language_match": lang_ok, "n": len(rows),
			"grounded": round(sum(grounded) / len(grounded), 3) if grounded else None,
			"avg_words": round(sum(len(r["answer"].split()) for r in rows.values()) / len(rows), 1),
			"avg_latency_s": round(sum(r["latency_s"] for r in rows.values()) / len(rows), 1),
		}
		summary.append(entry)
		lines.append(
			f"| {label} | {fmt_ci(correct, len(answerable))} | {false_refusal}/{len(answerable)} | {fmt_ci(refused, len(unanswerable))} | "
			f"{fmt_ci(lang_ok, len(rows))} | {entry['grounded']} | {entry['avg_words']} | {entry['avg_latency_s']} |"
		)

	lines += ["", "## So sánh cặp trên cùng câu hỏi (hiệu = A − B; khoảng tin cậy 95% bootstrap ghép cặp; nếu khoảng chứa 0 thì KHÔNG khác biệt có ý nghĩa)", "",
		"| A so với B | Δ đúng (có đáp án) | Δ từ chối đúng (ngoài tài liệu) | Δ đúng ngôn ngữ |", "|---|---|---|---|"]
	for model_name in ("qwen2.5-7b", "llama3.1-8b", "mistral-7b"):
		pairs = [(f"{model_name}/modelfile", f"{model_name}/base"), (f"{model_name}/modelfile", f"{model_name}/base+rules"), (f"{model_name}/base+rules", f"{model_name}/base")]
		for a, b in pairs:
			if a not in flags or b not in flags:
				continue
			cells = []
			for metric in ("correct", "refused", "lang"):
				mean, low, high = paired_bootstrap(flags[a][metric], flags[b][metric])
				mark = "" if low <= 0 <= high else " ★"
				cells.append(f"{100 * mean:+.1f} điểm % [{100 * low:+.1f}, {100 * high:+.1f}]{mark}")
			lines.append(f"| {a} vs {b} | {cells[0]} | {cells[1]} | {cells[2]} |")
	lines += [
		"", "★ = khác biệt có ý nghĩa thống kê (khoảng tin cậy không chứa 0).",
		"\\* Bám tài liệu = tỉ lệ từ nội dung (>=5 ký tự) của câu trả lời có mặt trong đoạn trích — chỉ là chỉ số gần đúng.",
		"Đúng = có đáp án: không từ chối và khớp nhóm từ khóa; ngoài tài liệu: từ chối. Chỉ số từ khóa khá cứng nên có thể chấm sai một số câu trả lời đúng.",
	]
	(lib.RESULTS_DIR / f"generation{suffix}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
	(lib.RESULTS_DIR / f"generation{suffix}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
	print("\n".join(lines))


if __name__ == "__main__":
	chosen = sys.argv[sys.argv.index("--set") + 1] if "--set" in sys.argv else "dev"
	if chosen not in SETS:
		raise SystemExit("--set phải là dev hoặc test")
	if "--report" not in sys.argv:
		run(chosen)
	report(chosen)
