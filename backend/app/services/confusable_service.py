# Backlog 3.3: luyện cặp từ dễ nhầm (affect/effect...) dạng chọn từ điền chỗ trống.
# Ngân hàng cố định (không gọi LLM): đáp án luôn đúng và không tốn lượt/thời gian chờ model.
import random
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import adaptive_service
from app.services.vi_contrast import CONTRAST

# (từ A, từ B, ghi chú tiếng Việt, [(câu có "___", đáp án là A hay B)])
_PAIRS: list[tuple[str, str, str, list[tuple[str, str]]]] = [
	("affect", "effect", "affect (động từ) = ảnh hưởng; effect (danh từ) = tác động, hiệu quả.",
		[("The new law will ___ thousands of workers.", "affect"), ("Sleep has a strong ___ on memory.", "effect")]),
	("advice", "advise", "advice /s/ là danh từ (lời khuyên); advise /z/ là động từ (khuyên).",
		[("Can you give me some ___ about my essay?", "advice"), ("I ___ you to book early.", "advise")]),
	("accept", "except", "accept = chấp nhận; except = ngoại trừ.",
		[("She decided to ___ the job offer.", "accept"), ("Everyone came ___ Tom.", "except")]),
	("then", "than", "then = lúc đó, sau đó; than dùng trong so sánh hơn.",
		[("This book is better ___ the film.", "than"), ("Finish your work, ___ you can relax.", "then")]),
	("lose", "loose", "lose = đánh mất; loose = lỏng, rộng.",
		[("Don't ___ your passport at the airport.", "lose"), ("These trousers are too ___ for me.", "loose")]),
	("quiet", "quite", "quiet = yên tĩnh; quite = khá, hoàn toàn.",
		[("Please be ___ in the library.", "quiet"), ("The test was ___ difficult.", "quite")]),
	("principal", "principle", "principal = hiệu trưởng/chính; principle = nguyên tắc.",
		[("The ___ announced the new timetable.", "principal"), ("Honesty is a basic ___ of good science.", "principle")]),
	("rise", "raise", "rise (nội động từ) = tăng lên, tự dâng; raise (ngoại động từ) = nâng lên, làm tăng.",
		[("Prices tend to ___ every summer.", "rise"), ("The company plans to ___ salaries next year.", "raise")]),
	("economic", "economical", "economic = thuộc kinh tế; economical = tiết kiệm.",
		[("The country faces serious ___ problems.", "economic"), ("A small car is more ___ to run.", "economical")]),
	("borrow", "lend", "borrow = mượn (của người khác); lend = cho mượn.",
		[("Can I ___ your pen for a moment?", "borrow"), ("Could you ___ me ten dollars?", "lend")]),
	("beside", "besides", "beside = bên cạnh; besides = ngoài ra, hơn nữa.",
		[("She sat ___ her brother on the bus.", "beside"), ("I'm too tired. ___, it's raining.", "besides")]),
	("through", "though", "through = xuyên qua; though = mặc dù.",
		[("We walked ___ the forest at night.", "through"), ("___ it was late, they kept working.", "though")]),
	("make", "do", "make = tạo ra (kết quả); do = thực hiện (hành động, việc nhà).",
		[("I need to ___ a decision by Friday.", "make"), ("Have you ___ your homework yet?", "do")]),
	("job", "work", "job = công việc cụ thể (đếm được); work = công việc nói chung (không đếm được).",
		[("She found a new ___ in a bank.", "job"), ("I have a lot of ___ to finish today.", "work")]),
]
_TOTAL = sum(len(pair[3]) for pair in _PAIRS)


def _public(pair_index: int, item_index: int) -> dict:
	a, b, _, items = _PAIRS[pair_index]
	options = [a, b]
	random.shuffle(options)
	return {"question_id": f"{pair_index}.{item_index}", "sentence": items[item_index][0], "options": options}


def make_quiz(count: int) -> list[dict]:
	"""Rút ngẫu nhiên `count` câu: mỗi cặp 1 câu trước, thiếu thì bù câu còn lại của các cặp đã rút."""
	count = min(count, _TOTAL)
	pool = list(range(len(_PAIRS)))
	random.shuffle(pool)
	picks = [(p, random.randrange(len(_PAIRS[p][3]))) for p in pool[:count]]
	for p in pool:
		if len(picks) >= count:
			break
		other = [i for i in range(len(_PAIRS[p][3])) if (p, i) not in picks]
		if other:
			picks.append((p, other[0]))
	return [_public(p, i) for p, i in picks]


async def grade_quiz(db: AsyncSession, user_id: uuid.UUID, answers: list[dict]) -> dict:
	"""Chấm trên server (client không biết đáp án); câu sai ghi user_errors loại vocabulary."""
	results, correct = [], 0
	for answer in answers:
		try:
			pair_index, item_index = (int(part) for part in answer["question_id"].split("."))
			a, b, hint, items = _PAIRS[pair_index]
			sentence, right = items[item_index]
		except (ValueError, IndexError):
			raise ValueError("invalid_question") from None
		choice = answer["choice"].strip().lower()
		if choice not in (a, b):
			raise ValueError("invalid_question")
		is_correct = choice == right
		correct += is_correct
		if not is_correct:
			adaptive_service.record_error(
				db,
				user_id,
				"vocabulary",
				{
					"source": "confusable_pair",
					"original_text": sentence.replace("___", choice),
					"corrected_text": sentence.replace("___", right),
					"explanation": hint,
				},
			)
		results.append({"question_id": answer["question_id"], "is_correct": is_correct, "correct_answer": right, "explanation_vi": hint, "contrast_vi": None if is_correct else CONTRAST["confusable"]})
	if len(results) > correct:
		await db.commit()
	return {"score": correct, "total": len(results), "results": results}
