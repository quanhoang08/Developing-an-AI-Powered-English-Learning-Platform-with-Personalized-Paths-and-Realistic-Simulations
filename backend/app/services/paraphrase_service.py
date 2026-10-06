# Backlog 3.4: ngân hàng paraphrase — câu gốc + cách viết lại mẫu theo kỹ thuật (IELTS Writing/Speaking).
# Khác "Rephrase" của Writing (AI viết lại câu của chính người học): đây là kho mẫu cố định để luyện,
# không gọi LLM. Kiểm tra bài người học bằng độ giống (thứ tự từ) với câu gốc, không chấm nghĩa.
import re
from difflib import SequenceMatcher

TECHNIQUES = ("synonyms", "voice", "structure", "nominalisation")

# (kỹ thuật, câu gốc, [paraphrase mẫu], ghi chú tiếng Việt)
_BANK: list[tuple[str, str, list[str], str]] = [
	("synonyms", "Many people think that technology makes life easier.",
		["A large number of individuals believe that technology simplifies daily life."],
		"Thay từ khóa bằng từ đồng nghĩa: many people → a large number of individuals; think → believe; easier → simpler."),
	("synonyms", "The number of students has increased significantly.",
		["There has been a considerable rise in the number of learners."],
		"increase → rise; significantly → considerably; students → learners."),
	("synonyms", "Pollution is a serious problem in big cities.",
		["Contamination poses a grave threat in major urban areas."],
		"serious → grave; big cities → major urban areas; dùng động từ mạnh hơn (poses a threat)."),
	("synonyms", "Children spend too much time on their phones.",
		["Young people devote an excessive amount of time to their mobile devices."],
		"children → young people; spend → devote; phones → mobile devices."),
	("voice", "The government should reduce taxes.",
		["Taxes should be reduced by the government."],
		"Chủ động → bị động: should + be + V3. Đưa đối tượng chịu tác động lên đầu câu."),
	("voice", "Scientists have discovered a new species of frog.",
		["A new species of frog has been discovered by scientists."],
		"have + V3 → has been + V3; đổi chủ ngữ để nhấn vào kết quả."),
	("voice", "People often misunderstand this rule.",
		["This rule is often misunderstood."],
		"Bỏ chủ ngữ chung chung (people) khi dùng bị động — gọn hơn."),
	("voice", "The company will build a new factory next year.",
		["A new factory will be built by the company next year."],
		"will + V → will be + V3."),
	("structure", "Although the exam was difficult, most students passed.",
		["Most students passed despite the difficulty of the exam."],
		"although + mệnh đề → despite + cụm danh từ."),
	("structure", "Because the weather was bad, the match was cancelled.",
		["The match was cancelled owing to the bad weather."],
		"because + mệnh đề → owing to / due to + cụm danh từ."),
	("structure", "If you study hard, you will pass the test.",
		["Students who study hard will pass the test."],
		"Mệnh đề if → mệnh đề quan hệ (who + V) làm định ngữ cho chủ ngữ."),
	("structure", "He is too young to drive.",
		["He is not old enough to drive."],
		"too + adj + to V → not + adj ngược nghĩa + enough + to V."),
	("nominalisation", "Cities have grown quickly, which has caused many problems.",
		["The rapid growth of cities has caused many problems."],
		"Đổi động từ/trạng từ thành danh từ: grown quickly → rapid growth."),
	("nominalisation", "People are using the internet more often than before.",
		["There is an increased use of the internet."],
		"Dùng cụm danh từ (an increased use of) thay vì mệnh đề — văn học thuật hơn."),
	("nominalisation", "Many young people cannot find jobs, and this worries the government.",
		["Youth unemployment is a concern for the government."],
		"Gộp ý bằng danh từ ghép: cannot find jobs → unemployment."),
	("nominalisation", "The economy declined sharply, so many people lost their savings.",
		["The sharp decline of the economy led to widespread loss of savings."],
		"decline sharply → sharp decline; so → led to."),
]

_WORD = re.compile(r"[a-z']+")


def list_bank(technique: str | None) -> list[dict]:
	if technique is not None and technique not in TECHNIQUES:
		raise ValueError("invalid_technique")
	return [
		{"id": i, "technique": t, "original": original}
		for i, (t, original, _, _) in enumerate(_BANK)
		if technique is None or t == technique
	]


def similarity(original: str, attempt: str) -> float:
	"""Độ giống theo thứ tự từ (0-1): chép lại gần nguyên câu thì cao; đổi từ hoặc đảo cấu trúc (bị động...) thì thấp."""
	return round(SequenceMatcher(None, _WORD.findall(original.lower()), _WORD.findall(attempt.lower())).ratio(), 2)


def check_attempt(bank_id: int, attempt: str) -> dict:
	"""Trả mẫu + cảnh báo nếu bài làm giống >= 75% câu gốc (chưa thật sự paraphrase)."""
	if not 0 <= bank_id < len(_BANK):
		raise ValueError("paraphrase_not_found")
	technique, original, models, note = _BANK[bank_id]
	score = similarity(original, attempt)
	return {
		"technique": technique,
		"original": original,
		"similarity": score,
		"too_similar": score >= 0.75,
		"model_paraphrases": models,
		"note_vi": note,
	}
