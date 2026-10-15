# Dựng bộ bài Writing từ bài viết THẬT của người học (Cambridge English Write & Improve, BEA-2019 W&I+LOCNESS v2.1),
# mức CEFR do người chú thích của Cambridge gán, thay cho 12 bài AI tự soạn (writing_eval_set.json).
# Giấy phép dữ liệu: chỉ nghiên cứu/giáo dục phi thương mại, KHÔNG phân phối lại => file kết quả bị .gitignore; tải dữ liệu về rồi chạy:
#   https://www.cl.cam.ac.uk/research/nl/bea2019st/data/wi+locness_v2.1.bea19.tar.gz   (giải nén ra thư mục wi+locness/)
#   python experiments/make_bea_set.py <thư mục wi+locness> [số bài mỗi mức, mặc định 10]   # -> experiments/writing_eval_bea.json
# Đề bài gốc không được công bố cùng dữ liệu nên mọi bài dùng một đề chung chung; nhóm g0..gN = 1 bài mỗi mức để tái dùng thống kê "điểm tăng theo mức".
import json
import random
import sys
from pathlib import Path

LEVELS = ["A2", "B1", "B2", "C1"]
PROMPT = "Write about a topic of your choice (a letter, a story or an opinion), as clearly as you can."


def main() -> None:
	root, per_level = Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 10
	pools: dict[str, list[dict]] = {lv: [] for lv in LEVELS}
	for path in sorted((root / "json").glob("[ABC].*.json")):
		for line in path.read_text(encoding="utf-8").split("\n"):
			if not line.strip():
				continue
			row = json.loads(line)
			level = row["cefr"][:2]
			if level in pools and 120 <= len(row["text"].split()) <= 300:  # đủ dài để chấm, đủ ngắn để chạy nhanh trên GPU 6 GB
				pools[level].append(row)
	rng = random.Random(42)
	picked = {lv: rng.sample(pools[lv], per_level) for lv in LEVELS}
	essays = [{"prompt": f"g{i}", "level": lv, "text": picked[lv][i]["text"], "bea_id": picked[lv][i]["id"], "bea_cefr": picked[lv][i]["cefr"]} for i in range(per_level) for lv in LEVELS]
	data = {"note": "Bài THẬT của người học từ Cambridge English Write & Improve (BEA-2019), mức CEFR do người chú thích Cambridge gán; đề gốc không có nên dùng đề chung. Chỉ dùng phi thương mại, không phân phối lại.",
		"prompts": {f"g{i}": PROMPT for i in range(per_level)}, "essays": essays}
	out = Path(__file__).resolve().parent / "writing_eval_bea.json"
	out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
	print(f"{len(essays)} essays ({per_level}/level {', '.join(LEVELS)}) -> {out.name}; pool sizes: { {lv: len(p) for lv, p in pools.items()} }")


if __name__ == "__main__":
	main()
