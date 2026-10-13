# Thực nghiệm độ chính xác của bộ đếm cấu trúc câu bằng luật (app/utils/text_metrics.sentence_structures, backlog 2.6).
# 40 câu do tác giả tự viết và tự gán nhãn (loại câu + cấu trúc nâng cao), KHÔNG chọn theo luật nên có cả câu mà luật
# đã biết là bỏ sót ("that"-clause, chủ ngữ ghép dài). Chạy, không cần DB/LLM/Docker GPU:
#   docker exec -e PYTHONPATH=/app lumina_api python experiments/run_structure_eval.py     # -> results/structure_eval.md
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from app.utils.text_metrics import sentence_structures  # noqa: E402

TYPES = ["simple", "compound", "complex", "compound_complex"]
FEATURES = ["conditional", "passive", "relative_clause", "question"]

# (câu, loại đúng, cấu trúc nâng cao đúng)
CASES = [
	("The cat sat on the mat.", "simple", ""),
	("Tom and Mary went home.", "simple", ""),
	("She plays tennis every Sunday.", "simple", ""),
	("My brother works in a bank.", "simple", ""),
	("We visited the museum yesterday.", "simple", ""),
	("The children are playing in the garden.", "simple", ""),
	("He quickly finished his homework.", "simple", ""),
	("I like tea and coffee.", "simple", ""),
	("Public transport reduces traffic in big cities.", "simple", ""),
	("Do you like music?", "simple", "question"),
	("What time does the train leave?", "simple", "question"),
	("The window was broken by the boys.", "simple", "passive"),
	("English is spoken in many countries.", "simple", "passive"),
	("Houses are built from bricks.", "simple", "passive"),
	("I like tea, but she likes coffee.", "compound", ""),
	("It rained all day, so the match was cancelled.", "compound", "passive"),  # nhãn passive thêm sau khi rà dương tính giả
	("He studied hard, and he passed the exam.", "compound", ""),
	("She wanted to go out; her parents said no.", "compound", ""),
	("I called him, but he didn't answer.", "compound", ""),
	("We can take the bus, or we can walk.", "compound", ""),
	("The shop was closed and we went home.", "compound", "passive"),  # nhãn passive thêm sau khi rà dương tính giả
	("The movie was long but the acting was excellent.", "compound", ""),
	("He is tired, yet he keeps working.", "compound", ""),
	("Prices rose sharply and the government acted quickly.", "compound", ""),
	("Although it was raining, we went for a walk.", "complex", ""),
	("I stayed home because I was ill.", "complex", ""),
	("The man who lives next door is a doctor.", "complex", "relative_clause"),
	("When she arrived, the meeting had already started.", "complex", ""),
	("If you study hard, you will pass the test.", "complex", "conditional"),
	("She said that she was tired.", "complex", ""),
	("The book which I borrowed was very interesting.", "complex", "relative_clause"),
	("I will call you after I finish work.", "complex", ""),
	("Unless we act now, the problem will get worse.", "complex", "conditional"),
	("While he was cooking, the phone rang.", "complex", ""),
	("Although he was tired, he kept working, and he finished the report.", "compound_complex", ""),
	("I like tea, but she likes coffee because it keeps her awake.", "compound_complex", ""),
	("When the bell rang, the students left, and the teacher locked the door.", "compound_complex", ""),
	("If it rains, we will stay home, or we will watch a film.", "compound_complex", "conditional"),
	("The man who called me is my uncle, and he lives abroad.", "compound_complex", "relative_clause"),
	("She studied hard because she wanted a scholarship, so she passed easily.", "compound_complex", ""),
]


def main() -> None:
	confusion = {g: {p: 0 for p in TYPES} for g in TYPES}
	misses = []
	feature_counts = {f: {"tp": 0, "fp": 0, "fn": 0} for f in FEATURES}
	for text, gold, gold_features in CASES:
		result = sentence_structures(text)
		predicted = next(t for t in TYPES if result["types"][t] == 1)
		confusion[gold][predicted] += 1
		if predicted != gold:
			misses.append(f"- \"{text}\" — đúng: {gold}, luật: {predicted}")
		want = set(gold_features.split()) if gold_features else set()
		for feature in FEATURES:
			got = result["features"][feature] > 0
			counts = feature_counts[feature]
			counts["tp"] += got and feature in want
			counts["fp"] += got and feature not in want
			counts["fn"] += (not got) and feature in want
	correct = sum(confusion[t][t] for t in TYPES)
	lines = [f"# Thực nghiệm bộ đếm cấu trúc câu (luật, không LLM): {len(CASES)} câu tự viết và tự gán nhãn", "",
		f"**Độ chính xác loại câu: {correct}/{len(CASES)} ({correct / len(CASES):.0%})**", "",
		"## Ma trận nhầm lẫn (hàng = nhãn đúng, cột = luật dự đoán)", "",
		"| | " + " | ".join(TYPES) + " | Recall |", "|---|" + "---|" * (len(TYPES) + 1)]
	for g in TYPES:
		total = sum(confusion[g].values())
		lines.append(f"| {g} | " + " | ".join(str(confusion[g][p]) for p in TYPES) + f" | {confusion[g][g]}/{total} ({confusion[g][g] / total:.0%}) |")
	lines += ["", "## Cấu trúc nâng cao", "", "| Cấu trúc | TP | FP | FN | Precision | Recall |", "|---|---|---|---|---|---|"]
	for f, c in feature_counts.items():
		precision = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else float("nan")
		recall = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else float("nan")
		lines.append(f"| {f} | {c['tp']} | {c['fp']} | {c['fn']} | {precision:.0%} | {recall:.0%} |")
	lines += ["", "## Các câu luật nhận sai", ""] + (misses or ["(không có)"])
	lines += ["", "Hạn chế: bộ câu nhỏ (40) do chính tác giả viết nên không đại diện cho văn bản người học thật; "
		"luật dùng regex nên bỏ sót mệnh đề 'that' và chủ ngữ dài sau liên từ (xem ponytail trong text_metrics.py). "
		"Lần chạy đầu cho passive precision 38%; rà 5 dương tính giả thì 2 câu ('was cancelled', 'was closed') là bị động thật do tác giả gán thiếu nhãn "
		"(đã sửa nhãn), 3 câu còn lại là tính từ 'tired' bị luật nhầm là bị động — lỗi thật của luật."]
	(ROOT / "results" / "structure_eval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
	print("\n".join(lines))


if __name__ == "__main__":
	main()
