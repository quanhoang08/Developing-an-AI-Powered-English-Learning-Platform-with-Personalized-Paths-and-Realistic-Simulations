# Từ vựng theo chủ đề thi + độ phủ (backlog 3.5). Dữ liệu: NAWL 1.2 (từ học thuật, IELTS) và TSL 1.2
# (TOEIC Service List) của Browne và cộng sự, https://www.newgeneralservicelist.com, giấy phép
# CC BY-SA 4.0; file CSV gốc đặt trong app/data/wordlists. Mỗi dòng = 1 từ gốc + các dạng biến thể.
import json
import random
import re
import uuid
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vocab import VocabItem
from app.services import llm_service, reading_service
from app.services.vocab_service import create_vocab_item

_DIR = Path(__file__).resolve().parent.parent / "data" / "wordlists"
LISTS = {"nawl": "New Academic Word List (IELTS)", "tsl": "TOEIC Service List"}


@lru_cache(maxsize=None)
def _load(name: str) -> tuple[tuple[str, ...], dict[str, str]]:
	"""Trả (danh sách từ gốc theo thứ tự file, map dạng từ -> từ gốc)."""
	heads: list[str] = []
	forms: dict[str, str] = {}
	for line in (_DIR / f"{name}.csv").read_text(encoding="latin-1").splitlines():
		if not line.strip() or line.startswith("#"):
			continue
		variants = [v.strip().lower() for v in line.split(",") if v.strip()]
		heads.append(variants[0])
		for variant in variants:
			forms.setdefault(variant, variants[0])
	return tuple(heads), forms


@lru_cache(maxsize=1)
def _topics() -> dict[str, dict]:
	"""Từ vựng theo chủ đề do tác giả đề tài tự soạn (topics.json): {id: {title, words: [[từ, nghĩa tiếng Việt, (tùy chọn) câu ví dụ]]}}."""
	return json.loads((_DIR / "topics.json").read_text(encoding="utf-8"))


async def topic_overview(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
	"""Các chủ đề + từng từ đã lưu vào vocab của người học chưa (so khớp không phân biệt hoa/thường)."""
	known = {t.lower() for t in await db.scalars(select(VocabItem.term).where(VocabItem.user_id == user_id))}
	return [
		{
			"id": topic_id,
			"title": topic["title"],
			"words": [{"term": term, "meaning_vi": vi, "saved": term.lower() in known} for term, vi, *_ in topic["words"]],
		}
		for topic_id, topic in _topics().items()
	]


async def add_topic_words(db: AsyncSession, user_id: uuid.UUID, topic_id: str) -> list[VocabItem]:
	"""Thêm mọi từ chưa có của chủ đề vào vocab (SM-2). Nghĩa tiếng Việt có sẵn trong file nên không tốn lượt LLM."""
	topic = _topics().get(topic_id)
	if topic is None:
		raise ValueError("topic_not_found")
	known = {t.lower() for t in await db.scalars(select(VocabItem.term).where(VocabItem.user_id == user_id))}
	created = []
	for term, meaning_vi, *example in topic["words"]:
		if term.lower() in known:
			continue
		try:
			created.append(await create_vocab_item(db, user_id, term, meaning_vi, None, None, None, None, example[0] if example else None, [], [], unit_label=topic["title"]))
		except ValueError:
			continue  # trùng đồng thời: bỏ từ này
	return created


def _known_heads(terms: list[str], forms: dict[str, str]) -> set[str]:
	return {forms[t] for t in (x.strip().lower() for x in terms) if t in forms}


async def coverage(db: AsyncSession, user_id: uuid.UUID, name: str) -> dict:
	"""Bao nhiêu từ gốc của danh sách người học đã lưu vào vocab, kèm vài từ gợi ý chưa lưu."""
	heads, forms = _load(name)
	terms = list(await db.scalars(select(VocabItem.term).where(VocabItem.user_id == user_id)))
	known = _known_heads(terms, forms)
	missing = [h for h in heads if h not in known]
	return {
		"list": name,
		"title": LISTS[name],
		"total": len(heads),
		"known": len(known),
		"percent": round(100 * len(known) / len(heads), 1),
		"suggestions": random.sample(missing, min(8, len(missing))),
	}


def text_coverage(name: str, text: str) -> dict:
	"""Độ phủ của danh sách trong một đoạn văn: % số từ chạy thuộc danh sách + các từ gốc tìm thấy."""
	_, forms = _load(name)
	tokens = re.findall(r"[a-z]+", text.lower())
	hits = [forms[t] for t in tokens if t in forms]
	return {
		"list": name,
		"tokens": len(tokens),
		"percent": round(100 * len(hits) / len(tokens), 1) if tokens else 0.0,
		"words_found": sorted(set(hits)),
	}


async def add_words(db: AsyncSession, user_id: uuid.UUID, name: str, words: list[str]) -> list[VocabItem]:
	"""Thêm từ gợi ý của danh sách vào vocab (tra nghĩa bằng Ollama như /from-errors)."""
	heads, _ = _load(name)
	valid = set(heads)
	known = {t.lower() for t in await db.scalars(select(VocabItem.term).where(VocabItem.user_id == user_id))}
	created: list[VocabItem] = []
	for word in dict.fromkeys(w.strip().lower() for w in words):
		if word not in valid or word in known:
			continue
		try:
			info = await reading_service.lookup_term(word, f'The word "{word}" is on the {LISTS[name]}.')
			created.append(
				await create_vocab_item(
					db, user_id, word, info["definition"], None, None, info["ipa"], None,
					info["example_sentence"] or None, info["synonyms"], info["antonyms"],
				)
			)
		except (llm_service.AIServiceError, ValueError):
			continue
	return created
