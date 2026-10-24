# Hemingway-style + CEFR-ước-lượng cho bài viết (tài liệu tính năng: Hemingway Editor, TextInspector). Thuần luật + wordfreq,
# không LLM. CEFR theo tần suất Zipf chỉ là ƯỚC LƯỢNG (không phải danh sách CEFR chính thức).
import re

import wordfreq

LONG_SENTENCE = 20
VERY_LONG_SENTENCE = 30
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-z']+")
_PASSIVE_RE = re.compile(
	r"\b(?:am|is|are|was|were|be|been|being)\s+(?:\w+ed|known|made|done|given|taken|seen|written|built|found|held|kept|led|paid|sold|told|chosen|shown)\b",
	re.IGNORECASE,
)
_NOT_ADVERBS = {"only", "family", "early", "likely", "friendly", "lovely", "daily", "reply", "apply", "supply", "july", "italy", "belly", "jelly", "silly", "ugly", "holy", "lonely", "lively", "elderly", "monthly", "weekly", "yearly"}
# (Zipf tối thiểu, mức CEFR ước lượng)
_CEFR_BANDS = [(5.0, "A1"), (4.5, "A2"), (4.0, "B1"), (3.5, "B2"), (3.0, "C1"), (0.0, "C2")]


def cefr_of_word(word: str) -> str:
	zipf = wordfreq.zipf_frequency(word.lower(), "en")
	return next(level for threshold, level in _CEFR_BANDS if zipf >= threshold)


def _syllables(word: str) -> int:
	groups = re.findall(r"[aeiouy]+", word.lower())
	count = len(groups) - (1 if word.lower().endswith("e") and len(groups) > 1 else 0)
	return max(count, 1)


def analyze(text: str) -> dict:
	sentences = [s.strip() for s in _SENTENCE_RE.split(text.strip()) if s.strip()]
	per_sentence = []
	for sentence in sentences:
		length = len(_WORD_RE.findall(sentence))
		per_sentence.append(
			{
				"text": sentence,
				"words": length,
				"level": "very_long" if length > VERY_LONG_SENTENCE else "long" if length > LONG_SENTENCE else "ok",
				"passive": [m.group(0) for m in _PASSIVE_RE.finditer(sentence)],
			}
		)
	words = _WORD_RE.findall(text)
	adverbs = sorted({w.lower() for w in words if w.lower().endswith("ly") and len(w) > 4 and w.lower() not in _NOT_ADVERBS})
	levels: dict[str, int] = {level: 0 for _, level in reversed(_CEFR_BANDS)}
	hard_words = set()
	for word in words:
		if len(word) < 3:
			continue
		level = cefr_of_word(word)
		levels[level] += 1
		if level in ("C1", "C2"):
			hard_words.add(word.lower())
	syllables = sum(_syllables(w) for w in words)
	grade = (
		0.39 * (len(words) / max(len(sentences), 1)) + 11.8 * (syllables / max(len(words), 1)) - 15.59
		if words
		else 0.0
	)
	return {
		"word_count": len(words),
		"sentence_count": len(sentences),
		"grade_level": round(max(grade, 0.0), 1),
		"sentences": per_sentence,
		"long_sentences": sum(1 for s in per_sentence if s["level"] != "ok"),
		"passive_count": sum(len(s["passive"]) for s in per_sentence),
		"adverbs": adverbs,
		"hard_words": sorted(hard_words),
		"cefr_counts": levels,
	}
