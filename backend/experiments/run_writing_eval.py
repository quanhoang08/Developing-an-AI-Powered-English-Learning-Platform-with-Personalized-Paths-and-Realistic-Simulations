# Thực nghiệm độ tin cậy + độ phân biệt của bộ chấm Writing (llm_service.grade_open_essay, đúng prompt thật của app).
# 12 bài tự soạn (writing_eval_set.json) x N lần chạy lặp; chỉ đổi settings.ollama_model_name, không sửa code app.
#
# Chạy (trong container api, Ollama đang chạy):
#   docker exec -e PYTHONPATH=/app lumina_api python experiments/run_writing_eval.py run --models qwen2.5:7b-instruct-q4_K_M --repeats 3
#   docker exec -e PYTHONPATH=/app lumina_api python experiments/run_writing_eval.py summary    # -> results/writing_eval.md
# Kết quả THÔ lưu ở results/writing_eval/*.jsonl để đổi cách tính mà không phải chạy lại model.
import argparse
import asyncio
import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
OUT_DIR = ROOT / "results" / "writing_eval"
SET_FILE, REPORT, TITLE = ROOT / "writing_eval_set.json", ROOT / "results" / "writing_eval.md", "12 bài tự soạn"
LEVEL_SRC = "do người soạn gán (chưa có giám khảo người xác nhận)"
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

from app.core.config import get_settings  # noqa: E402
from app.services import llm_service  # noqa: E402


def _safe(model: str) -> str:
	return re.sub(r"[^\w.-]+", "_", model)


def _ranks(values: list[float]) -> list[float]:
	"""Hạng trung bình (xử lý đồng hạng) để tính Spearman không cần scipy."""
	order = sorted(range(len(values)), key=lambda i: values[i])
	ranks = [0.0] * len(values)
	i = 0
	while i < len(order):
		j = i
		while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
			j += 1
		for k in range(i, j + 1):
			ranks[order[k]] = (i + j) / 2 + 1
		i = j + 1
	return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
	rx, ry = _ranks(x), _ranks(y)
	mx, my = statistics.fmean(rx), statistics.fmean(ry)
	den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
	return sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / den if den else None


async def run_model(model: str, repeats: int) -> None:
	settings = get_settings()
	settings.ollama_model_name = model
	settings.ollama_writing_model_name = model  # grade_open_essay dùng model Writing riêng từ 2026-10-13
	settings.llm_provider = "ollama"
	data = json.loads(SET_FILE.read_text(encoding="utf-8"))
	rows = []
	for rep in range(repeats):
		for index, essay in enumerate(data["essays"]):
			start = time.perf_counter()
			error, result = None, None
			try:
				result = await llm_service.grade_open_essay(data["prompts"][essay["prompt"]], essay["text"])
			except Exception as exc:  # noqa: BLE001 - ghi nhận mọi lỗi model để thống kê, không dừng thực nghiệm
				error = getattr(exc, "code", None) or type(exc).__name__
			seconds = round(time.perf_counter() - start, 1)
			rows.append({"model": model, "essay": index, "prompt": essay["prompt"], "level": essay["level"], "rep": rep, "seconds": seconds, "error": error, "result": result})
			score = (result or {}).get("overall_score")
			print(f"  {model} rep{rep} {essay['prompt']:9} {essay['level']} -> overall={score} cefr={(result or {}).get('cefr_level')} {seconds}s {error or ''}", flush=True)
	(OUT_DIR / f"{_safe(model)}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def _load(path: Path) -> list[dict]:
	return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]  # không dùng splitlines(): nó tách cả ở U+2028 nằm trong chuỗi JSON


def _cefr_index(value) -> int | None:
	match = re.search(r"\b([ABC][12])\b", str(value or "").upper())
	return LEVELS.index(match.group(1)) if match else None


def stats(rows: list[dict]) -> dict:
	ok = [r for r in rows if r["result"] and isinstance(r["result"].get("overall_score"), (int, float))]
	by_essay: dict[int, list[float]] = {}
	for r in ok:
		by_essay.setdefault(r["essay"], []).append(float(r["result"]["overall_score"]))
	gold = [LEVELS.index(r["level"]) for r in ok]
	scores = [float(r["result"]["overall_score"]) for r in ok]
	# Mỗi (đề, lần chạy): điểm có tăng theo A2<B1<B2<C1 không?
	strict = loose = groups = 0
	for prompt in {r["prompt"] for r in ok}:
		for rep in {r["rep"] for r in ok}:
			seq = [float(r["result"]["overall_score"]) for r in sorted((r for r in ok if r["prompt"] == prompt and r["rep"] == rep), key=lambda r: LEVELS.index(r["level"]))]
			if len(seq) == 4:
				groups += 1
				strict += all(a < b for a, b in zip(seq, seq[1:]))
				loose += all(a <= b for a, b in zip(seq, seq[1:]))
	cefr = [(_cefr_index(r["result"].get("cefr_level")), LEVELS.index(r["level"])) for r in ok]
	cefr = [(p, g) for p, g in cefr if p is not None]
	sd = [statistics.pstdev(v) for v in by_essay.values() if len(v) > 1]
	spread = [max(v) - min(v) for v in by_essay.values() if len(v) > 1]
	level_means = {lv: round(statistics.fmean(s for s, g in zip(scores, gold) if LEVELS[g] == lv), 1) for lv in ("A2", "B1", "B2", "C1") if any(LEVELS[g] == lv for g in gold)}
	return {
		"n_calls": len(rows), "n_ok": len(ok), "spearman": spearman(scores, gold) if len(ok) > 2 else None,
		"strict": f"{strict}/{groups}", "loose": f"{loose}/{groups}",
		"sd_mean": statistics.fmean(sd) if sd else None, "range_mean": statistics.fmean(spread) if spread else None,
		"cefr_exact": sum(p == g for p, g in cefr) / len(cefr) if cefr else None,
		"cefr_within1": sum(abs(p - g) <= 1 for p, g in cefr) / len(cefr) if cefr else None,
		"level_means": level_means, "mean_s": statistics.fmean(r["seconds"] for r in rows),
	}


def _fmt(value, pct=False) -> str:
	if value is None:
		return "-"
	return f"{value * 100:.0f}%" if pct else f"{value:.2f}"


def summary() -> None:
	lines = [f"# Thực nghiệm bộ chấm Writing ({TITLE} x lần chạy lặp, rubric 4 tiêu chí kiểu IELTS Task 2)", "",
		f"Mức A2/B1/B2/C1 của bài: {LEVEL_SRC}. Spearman = tương quan hạng giữa mức gán và điểm tổng; "
		"'Tăng nghiêm ngặt' = số nhóm (đề, lần chạy) có điểm A2<B1<B2<C1; SD = độ lệch chuẩn điểm tổng giữa các lần chạy lặp cùng một bài (điểm 0-100).", "",
		"| Model | Lần gọi (lỗi) | Spearman | Tăng nghiêm ngặt | Tăng không giảm | SD TB | Biên độ TB | CEFR đúng | CEFR ±1 mức | Điểm TB A2/B1/B2/C1 | Giây/bài |", "|---|---|---|---|---|---|---|---|---|---|---|"]
	for path in sorted(OUT_DIR.glob("*.jsonl")):
		rows = _load(path)
		s = stats(rows)
		lm = s["level_means"]
		lines.append(f"| {rows[0]['model']} | {s['n_calls']} ({s['n_calls'] - s['n_ok']}) | {_fmt(s['spearman'])} | {s['strict']} | {s['loose']} | {_fmt(s['sd_mean'])} | {_fmt(s['range_mean'])} | {_fmt(s['cefr_exact'], True)} | {_fmt(s['cefr_within1'], True)} | {' / '.join(str(lm.get(k, '-')) for k in ('A2', 'B1', 'B2', 'C1'))} | {s['mean_s']:.1f} |")
	REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
	print("\n".join(lines))


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("command", choices=["run", "summary"])
	parser.add_argument("--models", default="qwen2.5:7b-instruct-q4_K_M")
	parser.add_argument("--repeats", type=int, default=3)
	parser.add_argument("--set", choices=["own", "bea"], default="own", help="bea = bài thật của người học từ make_bea_set.py")
	args = parser.parse_args()
	if args.set == "bea":
		global OUT_DIR, SET_FILE, REPORT, TITLE, LEVEL_SRC
		OUT_DIR, SET_FILE, REPORT = ROOT / "results" / "writing_eval_bea", ROOT / "writing_eval_bea.json", ROOT / "results" / "writing_eval_bea.md"
		TITLE = "bài thật của người học, BEA-2019 / Cambridge Write & Improve"
		LEVEL_SRC = "do người chú thích của Cambridge gán (BEA-2019)"
	OUT_DIR.mkdir(parents=True, exist_ok=True)
	if args.command == "summary":
		summary()
		return
	for model in args.models.split(","):
		asyncio.run(run_model(model.strip(), args.repeats))


if __name__ == "__main__":
	main()
