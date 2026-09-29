# Đọc phụ đề .srt và gộp các cue thành câu để đánh chỉ mục tìm cụm từ (Movie Context, video thật).
import re

_TIME = re.compile(r"(\d+):(\d\d):(\d\d)[,.](\d{1,3})\s*-->\s*(\d+):(\d\d):(\d\d)[,.](\d{1,3})")
_MARKUP = re.compile(r"<[^>]+>|\{\\[^}]*\}")
# Cue chỉ mô tả âm thanh: "[door slams]", "(laughs)", "♪ ... ♪" — không phải lời thoại.
_NON_SPEECH = re.compile(r"^[\[(♪#].*[\])♪#]?$")
_SENTENCE_END = re.compile(r"[.?!…][\"'”’)]*$")


def _ms(hours: str, minutes: str, seconds: str, fraction: str) -> int:
	return ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(fraction.ljust(3, "0"))


def read_text(path: str) -> str:
	# Phụ đề tải từ mạng lúc thì UTF-8 (có/không BOM), lúc thì Windows-1252.
	data = open(path, "rb").read()
	for encoding in ("utf-8-sig", "cp1252"):
		try:
			return data.decode(encoding)
		except UnicodeDecodeError:
			continue
	return data.decode("latin-1")


def parse_srt(text: str) -> list[tuple[int, int, str]]:
	"""[(start_ms, end_ms, text)] theo thứ tự thời gian; bỏ cue rỗng và cue mô tả âm thanh."""
	cues = []
	for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n")):
		lines = block.strip().split("\n")
		for position, line in enumerate(lines):
			match = _TIME.search(line)
			if not match:
				continue
			body = " ".join(part.strip() for part in lines[position + 1 :] if part.strip())
			body = re.sub(r"\s+", " ", _MARKUP.sub("", body)).strip()
			body = re.sub(r"^[-–]\s*", "", body)
			if body and not _NON_SPEECH.match(body):
				cues.append((_ms(*match.groups()[:4]), _ms(*match.groups()[4:]), body))
			break
	return sorted(cues)


def merge_cues(
	cues: list[tuple[int, int, str]], max_gap_ms: int = 1500, max_chars: int = 220
) -> list[tuple[int, int, str]]:
	"""Gộp cue liền nhau cho tới khi hết câu — idiom hay bị cắt ngang 2 cue ("a piece of" / "cake")."""
	merged: list[tuple[int, int, str]] = []
	for start, end, text in cues:
		if merged:
			prev_start, prev_end, prev_text = merged[-1]
			unfinished = not _SENTENCE_END.search(prev_text)
			if unfinished and start - prev_end <= max_gap_ms and len(prev_text) + len(text) < max_chars:
				merged[-1] = (prev_start, end, f"{prev_text} {text}")
				continue
		merged.append((start, end, text))
	return merged


def clip_cues(
	cues: list[tuple[int, int, str]], start_ms: int, end_ms: int | None
) -> list[tuple[int, int, str]]:
	"""Giữ cue nằm trong [start_ms, end_ms] và dời mốc về 0 theo đầu đoạn cắt."""
	kept = []
	for cue_start, cue_end, text in cues:
		if cue_start < start_ms or (end_ms is not None and cue_end > end_ms):
			continue
		kept.append((cue_start - start_ms, cue_end - start_ms, text))
	return kept
