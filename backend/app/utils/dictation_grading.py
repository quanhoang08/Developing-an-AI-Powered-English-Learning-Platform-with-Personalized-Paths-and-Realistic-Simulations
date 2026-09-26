# Chấm Dictation: diff cấp từ + khoảng cách ngữ âm — rule-based, KHÔNG dùng LLM (business
# rule mục 3.4 feature-listening.md: "giữ chi phí thấp và kết quả nhất quán"). Hàm thuần, không
# đụng DB/network, dễ unit test riêng — cùng nguyên tắc với text_extraction.py/word_frequency.py.
import difflib
import re

import jellyfish

# Đồng nghĩa/viết tắt hợp lệ (mục 3.4) — chỉ collapse chiều "dạng đầy đủ" → "dạng viết tắt"
# trên text NGƯỜI HỌC gõ, để so khớp công bằng với transcript gốc (thường lưu dạng viết tắt tự
# nhiên như lời nói thật). Giới hạn đã biết: nếu transcript gốc lại lưu dạng đầy đủ ("do not"),
# chiều ngược lại chưa được xử lý — trường hợp hiếm với transcript sinh từ giọng nói tự nhiên.
_EXPANDED_TO_CONTRACTED = {
	"do not": "don't", "does not": "doesn't", "did not": "didn't",
	"can not": "can't", "will not": "won't", "would not": "wouldn't",
	"could not": "couldn't", "should not": "shouldn't",
	"is not": "isn't", "are not": "aren't", "was not": "wasn't", "were not": "weren't",
	"have not": "haven't", "has not": "hasn't", "had not": "hadn't",
	"i am": "i'm", "you are": "you're", "we are": "we're", "they are": "they're",
	"he is": "he's", "she is": "she's", "it is": "it's", "that is": "that's",
	"what is": "what's", "who is": "who's", "there is": "there's", "here is": "here's",
	"i have": "i've", "you have": "you've", "we have": "we've", "they have": "they've",
	"i will": "i'll", "you will": "you'll", "he will": "he'll", "she will": "she'll",
	"it will": "it'll", "we will": "we'll", "they will": "they'll",
	"i would": "i'd", "you would": "you'd", "he would": "he'd", "she would": "she'd",
	"we would": "we'd", "they would": "they'd", "let us": "let's",
}  # fmt: skip
# Duyệt cụm dài trước để "can not"/"cannot" không bị 1 pattern ngắn hơn nuốt mất 1 phần.
_EXPANSION_PATTERNS = sorted(_EXPANDED_TO_CONTRACTED.items(), key=lambda pair: -len(pair[0]))

_WORD_RE = re.compile(r"[a-zA-Z']+")
_PHONETIC_CLOSE_MAX_DISTANCE = 1


def normalize_word(word: str) -> str:
	"""Hạ chữ thường + bỏ dấu câu bám quanh — không phân biệt hoa/thường và dấu câu thuần tuý
	theo đúng business rule mục 3.4."""
	match = _WORD_RE.search(word)
	return match.group(0).lower() if match else ""


def tokenize_submission(text: str) -> list[str]:
	"""Tách + chuẩn hoá bài gõ của người học, collapse "do not" -> "don't" trước khi tách từ
	(xem ghi chú _EXPANDED_TO_CONTRACTED) để khớp số lượng token với transcript gốc."""
	lowered = text.lower()
	for expanded, contracted in _EXPANSION_PATTERNS:
		lowered = re.sub(rf"\b{re.escape(expanded)}\b", contracted, lowered)
	return [normalize_word(token) for token in lowered.split() if normalize_word(token)]


def _phonetic_close(reference_word: str, typed_word: str) -> bool:
	"""Cùng mã Metaphone, hoặc lệch <= 1 ký tự trên mã Metaphone (mục 3.5, bước 2)."""
	ref_code = jellyfish.metaphone(reference_word)
	typed_code = jellyfish.metaphone(typed_word)
	if ref_code == typed_code:
		return True
	return jellyfish.levenshtein_distance(ref_code, typed_code) <= _PHONETIC_CLOSE_MAX_DISTANCE


def classify_error_type(
	reference_word: str, typed_word: str | None, is_rare_or_proper: bool
) -> str:
	"""3 nhánh phân loại theo mục 3.5, bước 2. typed_word=None nghĩa là từ bị bỏ trống hoàn
	toàn (missing) — spec không mô tả rõ cách tính khoảng cách ngữ âm khi không có gì để so
	sánh, nên áp dụng đơn giản hoá có chủ đích: bỏ trống 1 từ hiếm/tên riêng thường vì KHÔNG
	nhận ra mặt chữ (vocabulary), bỏ trống từ thông dụng thường vì nghe sót hẳn (listening_
	comprehension) — ghi rõ đây là suy luận hợp lý, không phải quy tắc gốc trong spec."""
	if typed_word is None:
		return "vocabulary" if is_rare_or_proper else "listening_comprehension"

	if _phonetic_close(reference_word, typed_word):
		return "vocabulary" if is_rare_or_proper else "spelling"
	return "listening_comprehension"


def _reference_tag_at(reference_tags: list[dict], index: int) -> bool:
	if 0 <= index < len(reference_tags):
		return bool(reference_tags[index].get("is_rare_or_proper"))
	return False


def diff_dictation(
	reference_words: list[str], reference_tags: list[dict], submitted_text: str
) -> tuple[list[dict], float]:
	"""So khớp cấp từ giữa reference_words (transcript gốc, đã đúng thứ tự) và bài gõ của
	người học. Trả về (errors, score) — errors theo đúng shape API `{ type, word, position }`
	(api-spec.md mục 4) cộng thêm error_type nội bộ (None với "extra", không phân loại được —
	xem docstring module) để listening_service ghi vào user_errors.

	"Người học bỏ trống hoàn toàn": submitted_text rỗng -> tokenize ra [] -> toàn bộ
	reference_words rơi vào 1 opcode 'delete' duy nhất -> tất cả thành lỗi missing, không cần
	xử lý riêng (mục 3.5, edge case đầu tiên).
	"""
	reference_normalized = [normalize_word(word) for word in reference_words]
	submitted_tokens = tokenize_submission(submitted_text)

	matcher = difflib.SequenceMatcher(a=reference_normalized, b=submitted_tokens, autojunk=False)
	errors: list[dict] = []
	correct_count = 0

	for tag, ref_start, ref_end, sub_start, sub_end in matcher.get_opcodes():
		if tag == "equal":
			correct_count += ref_end - ref_start
			continue

		if tag == "delete":
			for ref_index in range(ref_start, ref_end):
				word = reference_words[ref_index]
				is_rare = _reference_tag_at(reference_tags, ref_index)
				errors.append(
					{
						"type": "missing",
						"word": word,
						"position": ref_index,
						"error_type": classify_error_type(reference_normalized[ref_index], None, is_rare),
					}
				)
		elif tag == "insert":
			for sub_index in range(sub_start, sub_end):
				errors.append(
					{
						"type": "extra",
						"word": submitted_tokens[sub_index],
						# Vị trí neo theo mốc chèn trong reference — chưa có từ gốc để gán index riêng.
						"position": ref_start,
						"error_type": None,
					}
				)
		elif tag == "replace":
			ref_span = list(range(ref_start, ref_end))
			sub_span = list(range(sub_start, sub_end))
			# Ghép theo vị trí tương ứng trong đoạn replace; phần lệch dư xử lý như missing/extra.
			for offset, ref_index in enumerate(ref_span):
				word = reference_words[ref_index]
				is_rare = _reference_tag_at(reference_tags, ref_index)
				if offset < len(sub_span):
					typed = submitted_tokens[sub_span[offset]]
					errors.append(
						{
							"type": "wrong",
							"word": word,
							"position": ref_index,
							"error_type": classify_error_type(reference_normalized[ref_index], typed, is_rare),
						}
					)
				else:
					errors.append(
						{
							"type": "missing",
							"word": word,
							"position": ref_index,
							"error_type": classify_error_type(reference_normalized[ref_index], None, is_rare),
						}
					)
			if len(sub_span) > len(ref_span):
				for sub_index in sub_span[len(ref_span):]:
					errors.append(
						{"type": "extra", "word": submitted_tokens[sub_index], "position": ref_end, "error_type": None}
					)

	total = len(reference_words)
	score = round((correct_count / total) * 100, 2) if total else 0.0
	return errors, score
