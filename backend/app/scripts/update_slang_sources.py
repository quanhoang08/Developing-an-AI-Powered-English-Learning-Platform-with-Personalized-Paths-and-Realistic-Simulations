"""Ghi lại source_reference của slang_phrases theo kết quả đối chiếu thật (docs/doi_chieu_slang_tu_dien.md, 2026-10-13).

Nghĩa và ví dụ của MỌI cụm do công cụ AI soạn; cột này chỉ nói cụm đã được đối chiếu nghĩa với từ điển nào.
Cụm không có trong danh sách dưới đây được ghi "AI soạn, chưa đối chiếu từ điển". Không đổi schema; chạy lặp lại an toàn.

Chạy (trong container api):
  docker exec -e PYTHONPATH=/app lumina_api python -m app.scripts.update_slang_sources
"""
import asyncio
from collections import Counter

from sqlalchemy import select

from app.database import get_session_factory
from app.models.speaking import SlangPhrase

OXF = "Oxford Learner's Dictionaries (đối chiếu nghĩa)"
BOTH = "Oxford Learner's Dictionaries; Wiktionary (đối chiếu nghĩa)"
WIKI = "Wiktionary (đối chiếu nghĩa)"
NONE = "AI soạn, chưa đối chiếu từ điển"

CHECKED = {
	OXF: [
		"no worries", "my bad", "no big deal", "piece of cake", "break a leg", "long time no see", "fair enough", "no hard feelings",
		"cheer up", "with regard to", "break the ice", "under the weather", "hang in there", "bite the bullet", "on the same page",
		"rain check", "take your time", "over the moon", "out of the blue", "look forward to", "on the other hand",
		"at your earliest convenience", "in accordance with", "come up with",
	],
	BOTH: ["you bet", "no way", "take it easy", "keep an eye on", "figure out"],
	WIKI: [
		"hang out", "sounds good", "cut it out", "give it a shot", "what's up", "keep me posted", "hit the books", "call it a night",
		"heads up", "i'm all ears", "hit the sack", "take care of", "get along with",
	],
}
SOURCE_OF = {phrase: source for source, phrases in CHECKED.items() for phrase in phrases}


async def main() -> None:
	async with get_session_factory()() as db:
		rows = (await db.execute(select(SlangPhrase))).scalars().all()
		for row in rows:
			row.source_reference = SOURCE_OF.get(row.phrase_text.lower().replace("’", "'"), NONE)
		await db.commit()
	print(dict(Counter(row.source_reference for row in rows)))


if __name__ == "__main__":
	asyncio.run(main())
