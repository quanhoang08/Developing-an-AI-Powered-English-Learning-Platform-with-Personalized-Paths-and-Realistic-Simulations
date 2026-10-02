# Hàm thuần đo văn bản bằng luật (không LLM, không DB): cấu trúc câu của bài Writing (backlog 2.6)
# và chỉ số trôi chảy của lượt nói Speaking (backlog 2.4).
import re

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[a-zA-Z']+")
_SUBORDINATE_RE = re.compile(
	r"\b(although|though|because|since|while|whereas|when|whenever|after|before|until|unless|if|as soon as)\b"
)
_RELATIVE_RE = re.compile(r"\b(who|whom|whose|which)\b")
_SUBJECT_PRONOUNS = r"(?:i|you|he|she|it|we|they|there|this|these|those)"
_AUX_VERBS = r"(?:is|are|was|were|has|have|had|will|would|can|could|did|does|do)"
# Câu ghép: liên từ có dấu phẩy/chấm phẩy, hoặc (không dấu phẩy) liên từ + chủ ngữ mới
# ("I like tea but she likes coffee", "it rained and the match was cancelled").
_COORDINATE_RE = re.compile(
	rf",\s*(?:and|but|or|so|yet)\b|;"
	rf"|\b(?:and|but|or|so|yet)\s+{_SUBJECT_PRONOUNS}\b"
	rf"|\b(?:and|but|or|so|yet)\s+(?:the|a|an|my|your|his|her|our|their)\s+\w+\s+{_AUX_VERBS}\b"
)
_CONDITIONAL_RE = re.compile(r"\b(if|unless)\b")
_PASSIVE_RE = re.compile(r"\b(is|are|was|were|be|been|being)\s+(\w+ed|\w+en|made|done|built|known|seen|found|given)\b")

# Từ đệm; "like" không có ở đây vì dùng đúng nghĩa rất thường gặp.
_FILLERS = {"um", "uh", "er", "erm", "hmm", "ah"}
_FILLER_PHRASES = ("you know", "i mean", "sort of", "kind of")


def sentence_structures(text: str) -> dict:
	"""Đếm câu đơn/ghép/phức/ghép-phức và vài cấu trúc nâng cao (Grammatical Range).

	ponytail: nhận diện bằng regex nên vẫn bỏ sót câu ghép có chủ ngữ là danh từ riêng/cụm dài sau liên từ
	("... and Tom left"); nâng cấp bằng parser (spaCy) nếu cần chính xác.
	"""
	types = {"simple": 0, "compound": 0, "complex": 0, "compound_complex": 0}
	features = {"conditional": 0, "passive": 0, "relative_clause": 0, "question": 0}
	sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]
	for sentence in sentences:
		lower = sentence.lower()
		is_complex = bool(_SUBORDINATE_RE.search(lower) or _RELATIVE_RE.search(lower))
		is_compound = bool(_COORDINATE_RE.search(lower))
		key = (
			"compound_complex" if is_complex and is_compound
			else "complex" if is_complex
			else "compound" if is_compound
			else "simple"
		)
		types[key] += 1
		features["conditional"] += bool(_CONDITIONAL_RE.search(lower))
		features["passive"] += bool(_PASSIVE_RE.search(lower))
		features["relative_clause"] += bool(_RELATIVE_RE.search(lower))
		features["question"] += sentence.endswith("?")
	return {
		"sentence_count": len(sentences),
		"types": types,
		"features": features,
		# Số loại cấu trúc khác nhau đã dùng (tối đa 8) — chỉ báo thô cho độ đa dạng.
		"distinct_structures": sum(v > 0 for v in types.values()) + sum(v > 0 for v in features.values()),
	}


def speech_metrics(text: str) -> dict:
	"""Số từ đệm và độ đa dạng từ vựng (từ khác nhau / tổng từ) của 1 lượt nói."""
	words = [w.lower() for w in _WORD_RE.findall(text)]
	lower = text.lower()
	fillers = sum(w in _FILLERS for w in words) + sum(lower.count(p) for p in _FILLER_PHRASES)
	return {
		"filler_count": fillers,
		"lexical_diversity": round(len(set(words)) / len(words), 2) if words else 0.0,
	}
