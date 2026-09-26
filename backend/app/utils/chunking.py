# Chiến lược chia chunk cho RAG (thuần Python, không đụng DB/network nên dễ unit test và benchmark).
# Ba chiến lược để so sánh trong thực nghiệm (backend/experiments/run_retrieval.py):
#   fixed     — chia cứng theo số từ (baseline cũ, hay cắt ngang câu)
#   paragraph — gom nguyên đoạn văn cho tới khi đủ cỡ
#   sentence  — gom nguyên câu, có chồng lấp (overlap) vài câu giữa 2 chunk liền kề
# Tài liệu song ngữ Anh–Việt: bộ tách câu nhận biết chữ hoa có dấu tiếng Việt, và mỗi dòng/đoạn
# (vd. cặp câu dịch "EN — VI") không bao giờ bị cắt ngang ở chiến lược paragraph.
import re

# Kết thúc câu: . ! ? … theo sau là khoảng trắng và chữ hoa/số/mở ngoặc (kể cả chữ hoa tiếng Việt có dấu).
_VI_UPPER = "ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ"
_SENTENCE_END = re.compile(r"(?<=[.!?…])[\"')\]]*\s+(?=[\"'(\[]*[A-Z" + _VI_UPPER + r"0-9])")
_ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "Mr.", "Mrs.", "Dr.", "Prof.", "No.", "TP.", "PGS.", "TS.")

# Ký tự tạm (private-use) thay dấu chấm của chữ viết tắt để bộ tách câu không cắt nhầm.
_DOT = chr(0xE000)

STRATEGIES = ("fixed", "paragraph", "sentence")


def _word_count(text: str) -> int:
	return len(text.split())


def split_paragraphs(text: str) -> list[str]:
	"""Mỗi dòng không rỗng là 1 đoạn (khớp cách extract_docx_text nối paragraph bằng '\\n')."""
	return [line.strip() for line in re.split(r"\n+", text) if line.strip()]


def split_sentences(text: str) -> list[str]:
	"""Tách câu cho tiếng Anh/Việt; giữ nguyên các chữ viết tắt phổ biến (e.g., Dr., TP.)."""
	sentences: list[str] = []
	for paragraph in split_paragraphs(text):
		# Che dấu chấm của chữ viết tắt trước khi tách để không bị coi là hết câu.
		protected = paragraph
		for abbreviation in _ABBREVIATIONS:
			protected = protected.replace(abbreviation, abbreviation.replace(".", _DOT))
		for part in _SENTENCE_END.split(protected):
			part = part.replace(_DOT, ".").strip()
			if part:
				sentences.append(part)
	return sentences


def fixed_chunks(text: str, max_words: int) -> list[str]:
	"""Baseline: cắt cứng mỗi max_words từ, không quan tâm ranh giới câu."""
	words = text.split()
	return [" ".join(words[start : start + max_words]) for start in range(0, len(words), max_words)]


def paragraph_chunks(text: str, max_words: int) -> list[str]:
	"""Gom nguyên đoạn cho tới khi thêm đoạn kế sẽ vượt max_words; đoạn quá dài thì cắt cứng."""
	chunks: list[str] = []
	current: list[str] = []
	current_words = 0
	for paragraph in split_paragraphs(text):
		size = _word_count(paragraph)
		if size > max_words:
			if current:
				chunks.append("\n".join(current))
				current, current_words = [], 0
			chunks.extend(fixed_chunks(paragraph, max_words))
			continue
		if current and current_words + size > max_words:
			chunks.append("\n".join(current))
			current, current_words = [], 0
		current.append(paragraph)
		current_words += size
	if current:
		chunks.append("\n".join(current))
	return chunks


def sentence_chunks(text: str, max_words: int, overlap_sentences: int = 1) -> list[str]:
	"""Gom nguyên câu; chunk sau lặp lại `overlap_sentences` câu cuối của chunk trước để không mất ngữ cảnh."""
	units: list[str] = []
	for sentence in split_sentences(text):
		# Câu dài hơn cả 1 chunk (hiếm) buộc phải cắt theo từ.
		units.extend(fixed_chunks(sentence, max_words) if _word_count(sentence) > max_words else [sentence])

	chunks: list[str] = []
	current: list[str] = []
	current_words = 0
	for unit in units:
		size = _word_count(unit)
		if current and current_words + size > max_words:
			chunks.append(" ".join(current))
			carry = current[-overlap_sentences:] if overlap_sentences > 0 else []
			# Phần lặp không được chiếm quá nửa chunk mới, tránh chunk toàn nội dung trùng.
			while carry and sum(_word_count(s) for s in carry) > max_words // 2:
				carry = carry[1:]
			current = list(carry)
			current_words = sum(_word_count(s) for s in current)
		current.append(unit)
		current_words += size
	# current luôn có ít nhất 1 câu mới (vừa append sau phần lặp) nên không bao giờ chỉ toàn nội dung trùng.
	if current:
		chunks.append(" ".join(current))
	return chunks


def chunk_document(
	text: str, strategy: str = "sentence", max_words: int = 150, overlap_sentences: int = 1
) -> list[str]:
	"""Điểm vào duy nhất cho pipeline ingest và cho thực nghiệm so sánh chiến lược."""
	if strategy == "fixed":
		return fixed_chunks(text, max_words)
	if strategy == "paragraph":
		return paragraph_chunks(text, max_words)
	if strategy == "sentence":
		return sentence_chunks(text, max_words, overlap_sentences)
	raise ValueError(f"unknown_chunk_strategy: {strategy}")
