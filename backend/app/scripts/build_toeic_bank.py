"""Dựng ngân hàng đề TOEIC-style đã kiểm chứng sẵn (backlog 2.7) để người học bấm Start là có đề ngay, đủ số câu.

Model tác giả mặc định là Gemini (chất lượng cao hơn Ollama 8B; chỉ chạy tay một lần, người học không tốn quota). Mỗi câu
phải qua 2 lượt giải độc lập (thứ tự lựa chọn xáo khác nhau) của model kiểm chứng và chỉ có đúng 1 đáp án chấp nhận
được trùng đáp án sinh thì mới vào bảng toeic_bank.

Chạy (trong container api):
  python -m app.scripts.build_toeic_bank --part 5 --target 60
  python -m app.scripts.build_toeic_bank --part 7 --target 12 --author ollama --verifier ollama   # không dùng Gemini
"""
import argparse
import asyncio

from sqlalchemy import select

from app.database import get_session_factory
from app.models.toeic import ToeicBankUnit
from app.services import llm_service, toeic_service

_BATCH = {2: 10, 3: 1, 4: 1, 5: 10, 6: 1, 7: 1}  # số câu (Part 2/5) hoặc bài (Part 3/4/6/7) xin mỗi lần gọi
_MAX_FAILURES = 5  # lỗi LLM tích lũy trong một lần chạy trước khi bỏ cuộc
_MAX_CALLS_PER_TARGET = 6  # chặn vòng lặp vô hạn khi tỉ lệ đạt kiểm chứng quá thấp


async def verified_flags(items: list[dict], provider: str) -> list[bool]:
	"""2 lượt giải độc lập với lựa chọn xáo khác nhau; câu nào cả 2 lượt đều chỉ chọn đúng đáp án sinh mới True."""
	flags = [True] * len(items)
	for _ in range(2):
		shuffled = [toeic_service.shuffle_options(it) for it in items]
		answers = await llm_service.solve_toeic_items(shuffled, provider)
		flags = [ok and set(a) == {it["correct_index"]} for ok, it, a in zip(flags, shuffled, answers)]
	return flags


def _units(part: int, items: list[dict], flags: list[bool]) -> list[dict]:
	"""Part 2/5: mỗi câu đạt là 1 unit. Part 6/7: cả bài, chỉ nhận khi >= 2 câu (Part 6: cả 3 chỗ trống) đạt."""
	good = [it for it, ok in zip(items, flags) if ok]
	if part in (2, 5):
		return [{"questions": [it]} for it in good]
	if part == 6 and len(good) == 3 or part in (3, 4, 7) and len(good) >= 2:
		return [{"questions": good}]
	return []


async def build(part: int, target: int, author: str, verifier: str) -> int:
	llm_service._GEMINI_TIMEOUT_SECONDS = 150  # sinh 10 câu/lần gọi mất > 30s mặc định
	factory = get_session_factory()
	added = 0
	async with factory() as db:
		existing = [u for (u,) in (await db.execute(select(ToeicBankUnit.unit).where(ToeicBankUnit.part == part))).all()]
		seen = {q["prompt"].lower() for u in existing for q in u["questions"]} | {(q.get("passage") or "")[:80] for u in existing for q in u["questions"] if part in toeic_service.SINGLE_PASSAGE}
		batch = 6 if author == "ollama" and part in (2, 5) else _BATCH[part]  # Ollama 8B: 10 câu/lần dễ quá timeout
		failures = 0
		pause = 20 if "gemini" in (author, verifier) else 0  # ~3 lời gọi/vòng: giữ dưới ~5 lời gọi/phút của gói miễn phí
		for call in range(_MAX_CALLS_PER_TARGET * max(1, target // batch + 1)):
			if added >= target:
				break
			await asyncio.sleep(pause)
			try:
				raw = toeic_service.clean_items(part, await llm_service.generate_toeic_items(part, batch, author))
				raw = [it for it in raw if it["prompt"].lower() not in seen and (it.get("passage") or "")[:80] not in seen] if part in (2, 5) else raw
				if part in (2, 5):
					raw = toeic_service.drop_repeated_distractors(raw)
				if not raw:
					continue
				units = _units(part, raw, await verified_flags(raw, verifier))
			except llm_service.AIServiceError as error:
				# Hết quota thì dừng hẳn; lỗi khác (Ollama timeout, JSON cụt...) chỉ mất một lần gọi.
				failures += 1
				print(f"  LLM lỗi ({error.code}) lần {failures}: {str(error)[:80]}", flush=True)
				if failures >= _MAX_FAILURES:
					print("  dừng.")
					break
				if error.code == "ai_quota_exceeded":
					await asyncio.sleep(70)  # giới hạn theo phút: chờ sang phút mới rồi thử lại
				continue
			for unit in units[: target - added]:
				if part in toeic_service.SINGLE_PASSAGE and (unit["questions"][0].get("passage") or "")[:80] in seen:
					continue  # bài trùng bài đã có
				db.add(ToeicBankUnit(part=part, unit=unit, source=author))
				seen |= {q["prompt"].lower() for q in unit["questions"]} | {(q.get("passage") or "")[:80] for q in unit["questions"]}
				added += 1
			await db.commit()
			print(f"  Part {part}: gọi {call + 1}, đã thêm {added}/{target}", flush=True)
	return added


def main() -> None:
	parser = argparse.ArgumentParser(description="Dựng ngân hàng đề TOEIC-style")
	parser.add_argument("--part", type=int, choices=sorted(_BATCH), required=True)
	parser.add_argument("--target", type=int, default=20, help="số đơn vị muốn thêm (Part 2/5: câu; Part 3/4/6/7: bài)")
	parser.add_argument("--author", default="gemini", choices=["gemini", "ollama"])
	parser.add_argument("--verifier", default="gemini", choices=["gemini", "ollama"])
	args = parser.parse_args()
	added = asyncio.run(build(args.part, args.target, args.author, args.verifier))
	print(f"Xong Part {args.part}: thêm {added} đơn vị")


if __name__ == "__main__":
	main()
