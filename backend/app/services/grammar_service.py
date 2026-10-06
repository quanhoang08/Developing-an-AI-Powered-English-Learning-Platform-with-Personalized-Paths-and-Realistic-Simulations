# Backlog 3.8: bản đồ ngữ pháp (test đầu vào theo chủ điểm), bài sửa lỗi, luyện vị trí từ loại.
# Ngân hàng cố định (không LLM, không migration): đáp án chắc chắn đúng, chấm ở server.
import random
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grammar import GrammarAttempt
from app.services import adaptive_service
from app.services.vi_contrast import CONTRAST

TOPICS = ["tenses", "articles", "prepositions", "agreement", "word_form", "error_correction"]
_NO_ARTICLE = "(no article)"


# (chủ điểm, câu, [đáp án đúng, ...nhiễu], giải thích tiếng Việt). Đáp án đúng luôn đứng đầu; xáo khi ra đề.
_BANK: list[tuple[str, str, list[str], str]] = [
	("tenses", "She ___ in London since 2019.", ["has lived", "lived", "is living", "lives"],
		"'since 2019' → hiện tại hoàn thành: has lived."),
	("tenses", "When I arrived, the film ___ already.", ["had started", "has started", "starts", "is starting"],
		"Hành động xảy ra trước một mốc quá khứ → quá khứ hoàn thành: had started."),
	("tenses", "I ___ you tomorrow if I have time.", ["will call", "call", "called", "would have called"],
		"Câu điều kiện loại 1: if + hiện tại, mệnh đề chính dùng will + V."),
	("tenses", "Look! It ___ outside.", ["is raining", "rains", "rained", "has rained"],
		"'Look!' chỉ việc đang diễn ra → hiện tại tiếp diễn."),
	("tenses", "He ___ TV when the phone rang.", ["was watching", "watched", "has watched", "watches"],
		"Hành động đang diễn ra thì bị cắt ngang → quá khứ tiếp diễn."),
	("tenses", "By the time you arrive, we ___ dinner.", ["will have finished", "finish", "finished", "are finishing"],
		"'By the time' + hiện tại, xong trước mốc tương lai → tương lai hoàn thành."),
	("articles", "It was ___ unusual idea.", ["an", "a", "some", _NO_ARTICLE],
		"'unusual' bắt đầu bằng nguyên âm /ʌ/ → an."),
	("articles", "I bought a car and a bike. ___ car is red.", ["The", "A", "An", _NO_ARTICLE],
		"Chiếc xe đã được nhắc đến → xác định → the."),
	("articles", "The sun rises in ___ east.", ["the", "a", "an", _NO_ARTICLE],
		"Phương hướng (the east, the north...) luôn có the."),
	("articles", "I usually have ___ breakfast at 7.", [_NO_ARTICLE, "the", "a", "an"],
		"Tên bữa ăn nói chung không dùng mạo từ."),
	("articles", "He is ___ best student in the class.", ["the", "a", "an", _NO_ARTICLE],
		"So sánh nhất luôn có the."),
	("articles", "She is ___ honest person.", ["an", "a", "some", _NO_ARTICLE],
		"'honest' có h câm, đọc /ˈɒnɪst/ bắt đầu bằng nguyên âm → an."),
	("prepositions", "I'm interested ___ learning Spanish.", ["in", "on", "at", "for"],
		"be interested in."),
	("prepositions", "The meeting is ___ Monday at 9 a.m.", ["on", "in", "at", "by"],
		"Thứ trong tuần dùng on."),
	("prepositions", "She is good ___ maths.", ["at", "in", "on", "for"],
		"be good at."),
	("prepositions", "We arrived ___ the airport an hour early.", ["at", "in", "to", "on"],
		"arrive at + nơi cụ thể (sân bay, nhà ga); arrive in + thành phố/quốc gia."),
	("prepositions", "He has been waiting ___ two hours.", ["for", "since", "during", "from"],
		"for + khoảng thời gian; since + mốc thời gian."),
	("prepositions", "I'm afraid ___ spiders.", ["of", "from", "at", "with"],
		"be afraid of."),
	("agreement", "The list of items ___ on the desk.", ["is", "are", "were", "be"],
		"Chủ ngữ chính là 'list' (số ít), không phải 'items'."),
	("agreement", "Each of the employees ___ a badge.", ["has", "have", "having", "are having"],
		"'Each of' + danh từ số nhiều vẫn đi với động từ số ít."),
	("agreement", "My brother and my sister ___ both teachers.", ["are", "is", "was", "be"],
		"Hai chủ ngữ nối bằng 'and' → số nhiều."),
	("agreement", "The news ___ surprising.", ["was", "were", "are", "have been"],
		"'news' là danh từ không đếm được → động từ số ít."),
	("agreement", "There ___ three books on the shelf.", ["are", "is", "was", "has"],
		"Sau 'There' chia theo danh từ đứng sau: three books → are."),
	("agreement", "Mathematics ___ my favourite subject.", ["is", "are", "were", "have"],
		"Tên môn học tận cùng -ics là số ít."),
	("word_form", "Her ___ to the project was impressive.", ["contribution", "contribute", "contributed", "contributory"],
		"Sau sở hữu cách (Her) cần danh từ: contribution."),
	("word_form", "She spoke ___ about her plans.", ["confidently", "confident", "confidence", "confide"],
		"Bổ nghĩa cho động từ 'spoke' cần trạng từ: confidently."),
	("word_form", "It is ___ to work in noisy places.", ["difficult", "difficulty", "difficultly", "difficulties"],
		"Sau 'is' cần tính từ: difficult."),
	("word_form", "The ___ of the new road reduced traffic.", ["construction", "construct", "constructive", "constructed"],
		"Sau 'The' và trước 'of' cần danh từ: construction."),
	("word_form", "He is a very ___ driver.", ["careful", "care", "carefully", "carelessly"],
		"Trước danh từ 'driver' cần tính từ: careful."),
	("word_form", "They were ___ surprised by the results.", ["extremely", "extreme", "extremity", "extremist"],
		"Bổ nghĩa cho tính từ 'surprised' cần trạng từ: extremely."),
	("error_correction", "Fix the error: She don't like coffee.",
		["She doesn't like coffee.", "She not like coffee.", "She doesn't likes coffee.", "She don't likes coffee."],
		"Chủ ngữ ngôi thứ ba số ít → doesn't + V nguyên mẫu."),
	("error_correction", "Fix the error: He go to school every day.",
		["He goes to school every day.", "He going to school every day.", "He gone to school every day.", "He go to schools every day."],
		"Hiện tại đơn, ngôi thứ ba số ít → thêm -es: goes."),
	("error_correction", "Fix the error: I have saw that film before.",
		["I have seen that film before.", "I have see that film before.", "I had saw that film before.", "I has seen that film before."],
		"have + quá khứ phân từ: seen (saw là quá khứ đơn)."),
	("error_correction", "Fix the error: She is more taller than her sister.",
		["She is taller than her sister.", "She is more tall than her sister.", "She is most tall than her sister.", "She is taller that her sister."],
		"Tính từ ngắn so sánh hơn thêm -er, không dùng 'more'; sau so sánh hơn là 'than'."),
	("error_correction", "Fix the error: He suggested me to take a break.",
		["He suggested that I take a break.", "He suggested me taking a break.", "He suggested to me take a break.", "He suggest me to take a break."],
		"suggest không đi với 'object + to V'; dùng suggest (that) + mệnh đề hoặc suggest + V-ing."),
	("error_correction", "Fix the error: There is many reasons to agree.",
		["There are many reasons to agree.", "There be many reasons to agree.", "There is many reason to agree.", "There are many reason to agree."],
		"'many reasons' số nhiều → There are; sau many là danh từ số nhiều."),
]


# Giải thích vì sao từng đáp án nhiễu sai, cùng thứ tự với _BANK và với options[1:] của mỗi câu.
_WHY: list[list[str]] = [
	["'since' đi với hiện tại hoàn thành; quá khứ đơn (lived) dành cho việc đã kết thúc.", "Hiện tại tiếp diễn không dùng với 'since 2019' để nói việc kéo dài từ quá khứ đến nay.", "Hiện tại đơn nói thói quen, không diễn đạt khoảng thời gian từ 2019 đến nay."],
	["Hiện tại hoàn thành không đi với mốc quá khứ 'arrived'.", "Hiện tại đơn không hợp với việc xảy ra trước một mốc quá khứ.", "Hiện tại tiếp diễn nói việc đang diễn ra bây giờ, không phải trước lúc tôi đến."],
	["Mệnh đề chính của điều kiện loại 1 cần will, không dùng hiện tại đơn.", "Quá khứ đơn không nói về việc sẽ làm ngày mai.", "would have + V3 là điều kiện loại 3 (quá khứ không có thật)."],
	["Hiện tại đơn nói thói quen/sự thật, không phải việc đang xảy ra lúc 'Look!'.", "Quá khứ đơn nói việc đã xong, không hợp với 'Look!'.", "Hiện tại hoàn thành nhấn kết quả/trải nghiệm, không tả việc đang diễn ra."],
	["Quá khứ đơn không diễn tả hành động đang diễn ra thì bị cắt ngang.", "Hiện tại hoàn thành không đi với mốc quá khứ 'when the phone rang'.", "Hiện tại đơn không hợp với mốc quá khứ 'rang'."],
	["Mệnh đề chính cần tương lai hoàn thành; hiện tại đơn chỉ dùng trong mệnh đề 'by the time'.", "Quá khứ đơn không nói về việc sẽ xong trước mốc tương lai.", "Hiện tại tiếp diễn không diễn đạt việc đã hoàn tất trước mốc tương lai."],
	["'a' dùng trước âm phụ âm; 'unusual' bắt đầu bằng nguyên âm.", "'some' không đi với danh từ đếm được số ít như 'idea'.", "Danh từ đếm được số ít 'idea' không thể đứng trơ trọi, cần mạo từ."],
	["Chiếc xe đã được nhắc ở câu trước nên cần 'the', không phải 'A'.", "'An' là mạo từ không xác định và dùng trước nguyên âm; ở đây cần 'The'.", "'car' là danh từ đếm được số ít, cần mạo từ."],
	["Phương hướng là duy nhất nên cần 'the', không dùng 'a'.", "Phương hướng là duy nhất nên cần 'the', không dùng 'an'.", "Phương hướng (the east) không bỏ mạo từ."],
	["Nói bữa ăn nói chung (usually) thì bỏ mạo từ; 'the' chỉ dùng cho bữa cụ thể.", "'a breakfast' chỉ dùng khi có mô tả (a big breakfast).", "'an' sai vì 'breakfast' bắt đầu bằng phụ âm, và tên bữa ăn không cần mạo từ."],
	["So sánh nhất 'best' phải có 'the', không dùng 'a'.", "So sánh nhất 'best' phải có 'the', không dùng 'an'.", "So sánh nhất 'best' không bỏ 'the'."],
	["'honest' có h câm, đọc bắt đầu bằng nguyên âm nên dùng 'an', không phải 'a'.", "'some' không dùng với danh từ đếm được số ít 'person'.", "'person' đếm được số ít, cần mạo từ."],
	["interested không đi với 'on'; cụm đúng là interested in.", "interested không đi với 'at'; cụm đúng là interested in.", "interested không đi với 'for'; cụm đúng là interested in."],
	["'in' dùng cho tháng/năm/mùa; thứ trong tuần dùng 'on'.", "'at' dùng cho giờ (at 9 a.m.), không dùng cho thứ.", "'by' chỉ hạn chót, không dùng để chỉ ngày diễn ra."],
	["Cụm cố định là good at, không phải good in.", "Cụm cố định là good at, không phải good on.", "Cụm cố định là good at, không phải good for."],
	["arrive in dùng với thành phố/quốc gia; sân bay là nơi cụ thể nên dùng at.", "arrive không đi với 'to'.", "arrive on dùng với ngày, không dùng với nơi chốn."],
	["'since' đi với mốc thời gian (since 2 p.m.), không đi với khoảng 'two hours'.", "'during' đi với sự kiện/giai đoạn (during the war), không đi với số lượng thời gian.", "'from' cần đi cùng 'to' hoặc mốc bắt đầu, không dùng với 'two hours'."],
	["'afraid from' không tồn tại; dùng afraid of.", "'afraid at' không tồn tại; dùng afraid of.", "'afraid with' không tồn tại; dùng afraid of."],
	["'items' chỉ bổ nghĩa; chủ ngữ chính 'list' là số ít nên không dùng 'are'.", "'were' là quá khứ số nhiều, sai cả thì lẫn số.", "'be' không dùng làm động từ chia ở hiện tại đơn."],
	["'Each' là số ít nên không dùng 'have'.", "'having' thiếu trợ động từ nên không làm động từ chính được.", "'are having' sai số và đổi nghĩa thành đang diễn ra."],
	["Hai chủ ngữ nối bằng 'and' là số nhiều nên không dùng 'is'.", "'was' là số ít quá khứ, không hợp chủ ngữ số nhiều hiện tại.", "'be' không dùng làm động từ chia ở hiện tại đơn."],
	["'news' không đếm được nên dùng số ít; 'were' là số nhiều.", "'are' là số nhiều, không hợp với 'news'.", "'have been' là số nhiều, không hợp với 'news'."],
	["Sau 'There' chia theo 'three books' (số nhiều) nên không dùng 'is'.", "'was' là số ít, không hợp với 'three books'.", "'has' không dùng sau 'There' để chỉ sự tồn tại."],
	["Mathematics tận cùng -s nhưng là số ít, không dùng 'are'.", "'were' là số nhiều quá khứ.", "'have' là số nhiều, không hợp với 'Mathematics'."],
	["'contribute' là động từ; sau 'Her' cần danh từ.", "'contributed' là động từ quá khứ; sau 'Her' cần danh từ.", "'contributory' là tính từ; sau 'Her' cần danh từ."],
	["'confident' là tính từ; bổ nghĩa cho động từ 'spoke' cần trạng từ.", "'confidence' là danh từ, không bổ nghĩa cho động từ.", "'confide' là động từ, không bổ nghĩa cho động từ khác."],
	["'difficulty' là danh từ; sau 'is' cần tính từ.", "'difficultly' hầu như không dùng; tính từ chuẩn là 'difficult'.", "'difficulties' là danh từ số nhiều; sau 'is' cần tính từ."],
	["'construct' là động từ; sau 'The' cần danh từ.", "'constructive' là tính từ (mang tính xây dựng); sau 'The' cần danh từ.", "'constructed' là quá khứ phân từ; sau 'The' cần danh từ."],
	["'care' là danh từ/động từ; trước 'driver' cần tính từ.", "'carefully' là trạng từ; trước danh từ cần tính từ.", "'carelessly' là trạng từ và nghĩa ngược lại."],
	["'extreme' là tính từ; bổ nghĩa cho tính từ 'surprised' cần trạng từ.", "'extremity' là danh từ, không bổ nghĩa cho tính từ.", "'extremist' là danh từ chỉ người, không bổ nghĩa cho tính từ."],
	["Thiếu trợ động từ: phủ định hiện tại đơn dùng doesn't + V.", "Sau doesn't động từ giữ nguyên mẫu (like), không thêm -s.", "Vẫn dùng sai 'don't' với ngôi thứ ba và thêm -s thừa."],
	["'going' thiếu trợ động từ is; cần thì hiện tại đơn goes.", "'gone' là quá khứ phân từ, cần trợ động từ; thói quen hằng ngày dùng goes.", "Vẫn thiếu -es cho động từ và sửa nhầm 'schools'."],
	["'have' phải đi với quá khứ phân từ 'seen', không phải 'see'.", "'had saw' sai: had + V3, mà saw là V2.", "'I' đi với 'have', không phải 'has'."],
	["'tall' là tính từ ngắn: dùng -er, không dùng 'more'.", "'most' là so sánh nhất; câu này so sánh hai người.", "So sánh hơn dùng 'than', không phải 'that'."],
	["suggest không đi với tân ngữ rồi V-ing như vậy; dùng 'that I take' hoặc 'taking'.", "'suggested to me take' sai cấu trúc; cần 'that I take'.", "Vừa sai thì ('suggest') vừa sai cấu trúc 'object + to V'."],
	["'be' không chia theo chủ ngữ; dùng 'are'.", "'is' và 'many reason' đều sai số với 'many reasons'.", "'are' đúng nhưng 'many' phải đi với danh từ số nhiều 'reasons'."],
]
assert len(_WHY) == len(_BANK) and all(len(w) == len(item[2]) - 1 for w, item in zip(_WHY, _BANK))


def _public(index: int) -> dict:
	topic, sentence, options, _ = _BANK[index]
	return {"question_id": str(index), "topic": topic, "sentence": sentence, "options": random.sample(options, len(options))}


def make_quiz(topic: str | None, count: int) -> list[dict]:
	"""topic=None → test đầu vào: chia đều các chủ điểm; có topic → rút ngẫu nhiên trong chủ điểm đó."""
	by_topic = {t: [i for i, item in enumerate(_BANK) if item[0] == t] for t in ([topic] if topic else TOPICS)}
	for ids in by_topic.values():
		random.shuffle(ids)
	picks: list[int] = []
	while len(picks) < count and any(by_topic.values()):
		for ids in by_topic.values():
			if ids and len(picks) < count:
				picks.append(ids.pop())
	random.shuffle(picks)
	return [_public(i) for i in picks]


async def grade_quiz(db: AsyncSession, user_id: uuid.UUID, answers: list[dict], quiz_topic: str | None = None) -> dict:
	"""Chấm trên server; câu sai ghi user_errors loại grammar. `by_topic` là bản đồ ngữ pháp của lượt làm này."""
	results, by_topic, wrong = [], {}, 0
	for answer in answers:
		try:
			topic, sentence, options, hint = _BANK[int(answer["question_id"])]
		except (ValueError, IndexError):
			raise ValueError("invalid_question") from None
		if answer["choice"] not in options:
			raise ValueError("invalid_question")
		right = options[0]
		is_correct = answer["choice"] == right
		stat = by_topic.setdefault(topic, {"correct": 0, "total": 0})
		stat["total"] += 1
		stat["correct"] += is_correct
		if not is_correct:
			wrong += 1
			adaptive_service.record_error(
				db,
				user_id,
				"grammar",
				{
					"source": "grammar_bank",
					"topic": topic,
					"original_text": f"{sentence} → {answer['choice']}",
					"corrected_text": right,
					"explanation": hint,
				},
			)
		why_chosen = None if is_correct else _WHY[int(answer["question_id"])][options.index(answer["choice"]) - 1]
		results.append({
			"question_id": answer["question_id"], "topic": topic, "is_correct": is_correct, "why_chosen_vi": why_chosen,
			"correct_answer": right, "explanation_vi": hint, "contrast_vi": None if is_correct else CONTRAST[topic],
		})
	previous = await db.scalar(
		select(GrammarAttempt)
		.where(GrammarAttempt.user_id == user_id, GrammarAttempt.topic == quiz_topic)
		.order_by(GrammarAttempt.created_at.desc())
		.limit(1)
	)
	db.add(GrammarAttempt(user_id=user_id, topic=quiz_topic, score=len(results) - wrong, total=len(results), by_topic=by_topic))
	await db.commit()
	return {
		"score": len(results) - wrong, "total": len(results), "results": results, "by_topic": by_topic,
		"previous_by_topic": previous.by_topic if previous else None,
	}


async def history(db: AsyncSession, user_id: uuid.UUID, limit: int = 10) -> list[GrammarAttempt]:
	rows = await db.scalars(
		select(GrammarAttempt).where(GrammarAttempt.user_id == user_id).order_by(GrammarAttempt.created_at.desc()).limit(limit)
	)
	return list(rows)


async def daily_lesson(db: AsyncSession, user_id: uuid.UUID) -> dict:
	"""Bài 3 phút/ngày: 6 câu của chủ điểm yếu nhất trong 5 lượt gần nhất (cần >= 2 câu mỗi chủ điểm);
	chưa có dữ liệu thì trộn các chủ điểm."""
	totals: dict[str, list[int]] = {}
	for attempt in await history(db, user_id, 5):
		for topic, stat in attempt.by_topic.items():
			t = totals.setdefault(topic, [0, 0])
			t[0] += stat["correct"]
			t[1] += stat["total"]
	rated = {t: c / n for t, (c, n) in totals.items() if n >= 2}
	if not rated:
		return {"topic": None, "reason_vi": "Chưa có dữ liệu — làm một bộ câu trộn các chủ điểm.", "questions": make_quiz(None, 6)}
	weakest = min(rated, key=rated.get)
	return {
		"topic": weakest,
		"reason_vi": f"Chủ điểm yếu nhất gần đây: {weakest} ({rated[weakest]:.0%} đúng).",
		"questions": make_quiz(weakest, 6),
	}
