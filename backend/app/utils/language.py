# Phát hiện nhanh ngôn ngữ của câu hỏi (Việt / Anh) để buộc câu trả lời RAG đúng ngôn ngữ.
# Model 7B hay "trôi" sang tiếng Việt khi tài liệu song ngữ, nên ngôn ngữ đích được quyết định bằng hàm
# xác định này rồi ghi thẳng vào prompt thay vì nhờ model tự đoán (xem experiments/results/generation.md).

# Ký tự chỉ có trong tiếng Việt (chữ có dấu thanh/mũ/móc và đ) — tiếng Anh gần như không bao giờ có.
_VI_CHARS = set("ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ")


def is_vietnamese(text: str) -> bool:
	letters = [ch for ch in text.lower() if ch.isalpha()]
	return bool(letters) and sum(1 for ch in letters if ch in _VI_CHARS) / len(letters) > 0.02


def language_name(text: str) -> str:
	"""'Vietnamese' hoặc 'English' — dùng thẳng trong prompt."""
	return "Vietnamese" if is_vietnamese(text) else "English"
