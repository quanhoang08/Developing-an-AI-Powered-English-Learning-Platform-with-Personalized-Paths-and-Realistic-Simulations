# Đo bộ đếm cấu trúc câu bằng luật (app/utils/text_metrics.sentence_structures) trên câu THẬT của Universal Dependencies
# English-EWT (CC BY-SA 4.0, cây cú pháp do người chú thích), thay cho 40 câu tự viết trong run_structure_eval.py.
# Nhãn "đơn/ghép/phức/ghép-phức" được SUY RA bằng luật từ cây phụ thuộc đã chú thích (không phải người gán trực tiếp loại câu),
# nên sai số của luật suy nhãn (hàm gold bên dưới) cũng nằm trong con số cuối.
# Dữ liệu: https://github.com/UniversalDependencies/UD_English-EWT (tải en_ewt-ud-dev.conllu). Chạy, không cần DB/LLM:
#   python experiments/run_structure_eval_ud.py <đường dẫn en_ewt-ud-dev.conllu>     # -> results/structure_eval_ud.md
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from app.utils.text_metrics import sentence_structures  # noqa: E402

TYPES = ["simple", "compound", "complex", "compound_complex"]
FEATURES = ["conditional", "passive", "relative_clause", "question"]
SUB_DEPS = {"advcl", "ccomp", "csubj", "acl:relcl"}
SKIP_DEPS = {"parataxis", "orphan", "vocative", "discourse", "list", "reparandum", "goeswith", "dep"}
SUBJ = ("nsubj", "csubj", "expl")


def read(path: Path):
	for block in path.read_text(encoding="utf-8").split("\n\n"):
		text, tokens = None, []
		for line in block.split("\n"):
			if line.startswith("# text = "):
				text = line[9:]
			elif line and not line.startswith("#"):
				f = line.split("\t")
				if f[0].isdigit():
					tokens.append({"id": int(f[0]), "lemma": f[2], "upos": f[3], "feats": f[5], "head": int(f[6]), "dep": f[7]})
		if text and tokens:
			yield text, tokens


def gold(tokens: list[dict]):
	"""(loại câu, tập cấu trúc nâng cao) suy ra từ cây phụ thuộc; None nếu câu không phù hợp để đánh giá."""
	kids = defaultdict(list)
	for t in tokens:
		kids[t["head"]].append(t)
	roots = kids[0]
	if len(roots) != 1 or any(t["dep"].split(":")[0] in SKIP_DEPS for t in tokens):
		return None
	has_subj = lambda t: any(c["dep"].split(":")[0] in SUBJ for c in kids[t["id"]])  # noqa: E731
	main, stack = 1, [roots[0]]
	while stack:  # vế đẳng lập có chủ ngữ riêng ("He came and went" dùng chung chủ ngữ => vẫn là câu đơn)
		node = stack.pop()
		for c in kids[node["id"]]:
			if c["dep"] == "conj":
				main += has_subj(c)
				stack.append(c)
	sub = 0
	conditional = False
	for t in tokens:
		if t["dep"] in SUB_DEPS:
			marks = [c["lemma"].lower() for c in kids[t["id"]] if c["dep"] == "mark"]
			if t["dep"] == "acl:relcl" or has_subj(t) or any(m != "to" for m in marks):
				sub += 1
				conditional |= t["dep"] == "advcl" and any(m in ("if", "unless") for m in marks)
	kind = {(False, False): "simple", (True, False): "compound", (False, True): "complex", (True, True): "compound_complex"}[(main > 1, sub > 0)]
	feats = {"conditional": conditional, "passive": any(t["dep"] in ("nsubj:pass", "csubj:pass") for t in tokens),
		"relative_clause": any(t["dep"] == "acl:relcl" for t in tokens)}
	return kind, feats


def main() -> None:
	path = Path(sys.argv[1])
	confusion = {g: Counter() for g in TYPES}
	counts = {f: Counter() for f in FEATURES}
	misses, skipped, kept = [], Counter(), 0
	for text, tokens in read(path):
		g = gold(tokens)
		if g is None or not (5 <= len(tokens) <= 35) or tokens[-1]["lemma"] not in (".", "?", "!"):
			skipped["không phù hợp (đa gốc/rời rạc/quá ngắn-dài/không kết thúc bằng dấu câu)"] += 1
			continue
		result = sentence_structures(text)
		if sum(result["types"].values()) != 1:
			skipped["luật tách thành ≠1 câu"] += 1
			continue
		kept += 1
		kind, feats = g
		feats["question"] = text.rstrip().endswith("?")
		predicted = next(t for t in TYPES if result["types"][t] == 1)
		confusion[kind][predicted] += 1
		if predicted != kind and len(misses) < 12:
			misses.append(f"- \"{text}\" — gold: {kind}, luật: {predicted}")
		for f in FEATURES:
			got = result["features"][f] > 0
			counts[f]["tp"] += got and feats[f]
			counts[f]["fp"] += got and not feats[f]
			counts[f]["fn"] += (not got) and feats[f]
	correct = sum(confusion[t][t] for t in TYPES)
	pct = lambda a, b: f"{a / b:.0%}" if b else "-"  # noqa: E731
	lines = [f"# Bộ đếm cấu trúc câu (luật) trên câu thật UD English-EWT dev: {kept} câu", "",
		f"**Độ chính xác loại câu: {correct}/{kept} ({pct(correct, kept)})**. Nhãn suy ra từ cây cú pháp do người chú thích (luật suy nhãn có sai số riêng).", "",
		"## Ma trận nhầm lẫn (hàng = nhãn gold, cột = luật dự đoán)", "", "| gold \\ luật | " + " | ".join(TYPES) + " | n | recall |", "|---|" + "---|" * (len(TYPES) + 2)]
	for g in TYPES:
		n = sum(confusion[g].values())
		lines.append(f"| {g} | " + " | ".join(str(confusion[g][p]) for p in TYPES) + f" | {n} | {pct(confusion[g][g], n)} |")
	lines += ["", "## Cấu trúc nâng cao", "", "| Cấu trúc | Gold dương | Precision | Recall |", "|---|---|---|---|"]
	for f in FEATURES:
		c = counts[f]
		lines.append(f"| {f} | {c['tp'] + c['fn']} | {pct(c['tp'], c['tp'] + c['fp'])} | {pct(c['tp'], c['tp'] + c['fn'])} |")
	lines += ["", f"Câu bị loại: {dict(skipped)}", "", "## Một số câu luật đoán sai", "", *misses]
	(ROOT / "results" / "structure_eval_ud.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
	print("\n".join(lines))


if __name__ == "__main__":
	main()
