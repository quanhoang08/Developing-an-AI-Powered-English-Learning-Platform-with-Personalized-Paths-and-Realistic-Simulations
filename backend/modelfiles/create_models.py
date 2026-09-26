# Tạo các model Ollama tùy biến (qua Modelfile) để AI trả lời BÁM SÁT tài liệu, không lan man.
# Mỗi model gốc (Qwen / Llama / Mistral) được "đóng gói" cùng SYSTEM prompt + tham số sinh cố định:
#   - SYSTEM: chỉ dùng đoạn trích, từ chối chuẩn khi tài liệu không có, trả lời theo ngôn ngữ câu hỏi, ngắn gọn.
#   - PARAMETER: temperature thấp, repeat_penalty, num_ctx đủ chứa 3–5 chunk, num_predict giới hạn độ dài.
# Chạy:  python modelfiles/create_models.py        (cần Ollama đang chạy và đã pull các model gốc)
# Kết quả: modelfiles/<tên>.Modelfile (để đưa vào báo cáo) và các model lumina-rag-* trong Ollama.
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # để import app.utils.language khi chạy như script

from app.utils.language import language_name  # noqa: E402

# Câu từ chối chuẩn theo ngôn ngữ câu hỏi — cố định để hệ thống và thực nghiệm nhận diện được
# (xem experiments/run_generation.py). v1 gộp cả hai vào một câu song ngữ làm model 7B trả lời tiếng
# Việt cho câu hỏi tiếng Anh, nên v2 tách riêng (kết quả v1 lưu ở experiments/results/generation_v1.md).
REFUSAL_EN = "The document does not cover this."
REFUSAL_VI = "Tài liệu không đề cập đến nội dung này."

SYSTEM_PROMPT = f"""You are Lumina, a study assistant for learners of English. You answer questions about a document the student uploaded. The excerpts and the question may each be in English, in Vietnamese, or a mix of both.

RULES
1. Use ONLY the numbered EXCERPTS in the user's message. Never use outside knowledge, even if you know the answer.
2. LANGUAGE: write the whole answer in the language given on the "ANSWER LANGUAGE" line, never in the language of the excerpts. English -> English answer even if the excerpts are Vietnamese; Vietnamese -> Vietnamese answer even if the excerpts are English. Keep words, example sentences and grammar forms quoted from the document in their original language.
3. If the excerpts do not contain the answer, reply with ONLY this sentence and nothing else: "{REFUSAL_EN}" for an English question, "{REFUSAL_VI}" for a Vietnamese question. Never add that sentence after a real answer.
4. Be concise: at most three sentences. Quote key terms exactly and cite the excerpt number, for example [1].
5. Do not add extra tips, extra examples or explanations that are not in the excerpts."""

# Few-shot cố định (chủ đề KHÁC hẳn corpus thực nghiệm để không rò dữ liệu đánh giá): (excerpt, câu hỏi, trả lời).
_EIFFEL = "[1] The Eiffel Tower was completed in 1889 and is 330 metres tall."
_PRESENT = "[1] Thì hiện tại đơn dùng để diễn tả thói quen hằng ngày, ví dụ: I get up at six."
FEW_SHOT = [
	(_EIFFEL, "Tháp Eiffel cao bao nhiêu?", "Tháp Eiffel cao 330 mét [1]."),
	(_PRESENT, "What is the simple present used for?", "It is used to express daily habits, for example: I get up at six [1]."),
	(_EIFFEL, "Who designed the Statue of Liberty?", REFUSAL_EN),
	(_PRESENT, "Thì tương lai đơn có cấu trúc thế nào?", REFUSAL_VI),
]

PARAMETERS = {
	"temperature": 0.1,
	"top_p": 0.9,
	"repeat_penalty": 1.1,
	"num_ctx": 4096,
	"num_predict": 300,
}

# (model gốc, tên model tùy biến)
MODELS = [
	("qwen2.5:7b-instruct-q4_K_M", "lumina-rag-qwen"),
	("llama3.1:8b", "lumina-rag-llama"),
	("mistral:7b", "lumina-rag-mistral"),
]


def render_modelfile(base: str) -> str:
	parameter_lines = "\n".join(f"PARAMETER {name} {value}" for name, value in PARAMETERS.items())
	shots = "\n".join(
		f'MESSAGE user """EXCERPTS:\n{excerpt}\n\nQUESTION: {question}\nANSWER LANGUAGE: {language_name(question)}"""\n'
		f'MESSAGE assistant """{answer}"""'
		for excerpt, question, answer in FEW_SHOT
	)
	return f'FROM {base}\n\n{parameter_lines}\n\nSYSTEM """{SYSTEM_PROMPT}"""\n\n{shots}\n'


def main() -> int:
	failures = 0
	for base, name in MODELS:
		path = HERE / f"{name}.Modelfile"
		path.write_text(render_modelfile(base), encoding="utf-8")
		result = subprocess.run(["ollama", "create", name, "-f", str(path)], capture_output=True, text=True)
		status = "ok" if result.returncode == 0 else f"FAILED: {result.stderr.strip()[-200:]}"
		failures += result.returncode != 0
		print(f"{name:20s} (FROM {base}) -> {status}")
	return 1 if failures else 0


if __name__ == "__main__":
	sys.exit(main())
