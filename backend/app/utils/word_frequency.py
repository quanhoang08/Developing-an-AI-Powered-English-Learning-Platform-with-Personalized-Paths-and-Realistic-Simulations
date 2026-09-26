# Hàm thuần gắn nhãn "từ hiếm/tên riêng" cho Dictation — không đụng DB/network, dễ unit test
# riêng (feature-listening.md mục 3.5, bước 1).
import re

import wordfreq

# wordfreq dùng thang Zipf (log10 của số lần xuất hiện/tỷ từ) — ngưỡng 3.3 là xấp xỉ tương
# đương "nằm trong ~5.000-8.000 từ tiếng Anh thông dụng nhất" mà spec yêu cầu (đối chiếu thủ
# công: "mitochondria"=3.09, "serendipity"=2.74 (hiếm, đúng) vs "pandemic"=3.68,
# "entrepreneur"=3.99 (thông dụng, đúng) — chấp nhận sai số nhỏ, đây là một ước lượng có chủ
# đích, không phải danh sách tần suất tự xây dựng).
_RARE_ZIPF_THRESHOLD = 3.3

_WORD_CHARS_RE = re.compile(r"[a-zA-Z']+")


def _strip_to_letters(word: str) -> str:
	# Bỏ dấu câu bám quanh từ (dấu phẩy, chấm câu...) trước khi tra tần suất/kiểm tra hoa.
	match = _WORD_CHARS_RE.search(word)
	return match.group(0) if match else ""


def is_proper_noun(word: str, is_sentence_start: bool) -> bool:
	"""Viết hoa NHƯNG không ở đầu câu → khả năng cao là tên riêng (NER đơn giản theo đúng
	mức độ mô tả trong feature-listening.md mục 3.5 — không dùng model NER thật, giới hạn đã
	biết là không xử lý được cụm tên riêng nhiều từ, xem mục 3.5 cuối)."""
	letters = _strip_to_letters(word)
	if not letters or is_sentence_start:
		return False
	return letters[0].isupper()


def is_rare_word(word: str) -> bool:
	"""Không nằm trong nhóm ~5.000-8.000 từ tiếng Anh thông dụng nhất, theo tần suất wordfreq."""
	letters = _strip_to_letters(word).lower()
	if not letters:
		return False
	return wordfreq.zipf_frequency(letters, "en") < _RARE_ZIPF_THRESHOLD


def tag_reference_words(words: list[str], sentence_start_indices: set[int]) -> list[dict]:
	"""Gắn nhãn is_rare_or_proper cho từng từ trong đoạn transcript được chọn cho 1 Dictation
	attempt. sentence_start_indices: tập chỉ số từ đứng đầu câu (không tính viết hoa đầu câu
	là dấu hiệu tên riêng)."""
	return [
		{
			"word": word,
			"is_rare_or_proper": (
				is_proper_noun(word, index in sentence_start_indices) or is_rare_word(word)
			),
		}
		for index, word in enumerate(words)
	]
