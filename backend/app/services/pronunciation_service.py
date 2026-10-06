# Phát âm cho người Việt (backlog 4.1-4.3, 4.5): câu mẫu theo lỗi hay gặp + chấm Azure có kịch bản,
# game cặp âm dễ nhầm, chế độ "nói thầm" (gõ thay nói). Ngân hàng cố định, không LLM, không migration.
import random
import re
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.gamification import ActivityLog
from app.services import llm_service, speaking_service, speech_service
from app.services.gamification_service import XP_BY_ACTIVITY, award_activity, day_start

SILENT_XP_DAILY_CAP = 5

_ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm", ".ogg"}

FOCUS_TIPS = {
	"final": "Tiếng Việt ít có phụ âm cuối nên hay nuốt âm cuối (-s, -t, -d, -k, -p). Hãy phát âm rõ âm cuối, dù nhẹ.",
	"cluster": "Cụm phụ âm (str-, spr-, -sts, -nds) không có trong tiếng Việt: đừng chèn nguyên âm vào giữa (\"sờ-trít\" -> \"street\").",
	"th": "/θ/ và /ð/: đặt đầu lưỡi giữa hai hàm răng rồi thổi hơi; đừng thay bằng /t/, /d/ hay /th/ của tiếng Việt.",
	"stress": "Tiếng Anh có trọng âm từ: nhấn mạnh, kéo dài âm tiết được nhấn và đọc lướt các âm còn lại (tiếng Việt thì các âm tiết đều nhau).",
	"ed": "Đuôi -ed đọc /t/, /d/ hoặc /ɪd/ tùy âm trước nó (walked = /t/, played = /d/, wanted = /ɪd/); đừng bỏ trống.",
}

# (id, trọng tâm, câu mẫu)
SENTENCES = [
	("f1", "final", "He asked for a cold drink and a hot cup of tea."),
	("f2", "final", "Please ask Jack to pick up the bags at the back."),
	("f3", "final", "She needs fresh bread, rice and eggs for lunch."),
	("c1", "cluster", "The strange street was crowded with students."),
	("c2", "cluster", "She spent six months studying in Spain."),
	("c3", "cluster", "The scripts describe the first three stages."),
	("t1", "th", "Thank you for these three things."),
	("t2", "th", "My brother thinks that this is the third path."),
	("t3", "th", "They thought the weather was rather worthless."),
	("s1", "stress", "The photographer took a photograph of the economy."),
	("s2", "stress", "It is important to understand the information."),
	("s3", "stress", "Our responsibility is to develop the technology."),
	("e1", "ed", "He walked, talked and worked all day."),
	("e2", "ed", "They wanted to rent a house, but we needed a different one."),
	("e3", "ed", "She asked, laughed and then helped us."),
]
_BY_ID = {sid: (focus, text) for sid, focus, text in SENTENCES}

# (từ A, từ B, ghi chú tiếng Việt)
PAIRS = [
	("ship", "sheep", "/ɪ/ ngắn và /iː/ dài: sheep kéo dài hơn, môi kéo ngang."),
	("bit", "beat", "/ɪ/ ngắn, lỏng; /iː/ dài, căng."),
	("full", "fool", "/ʊ/ ngắn và /uː/ dài, môi tròn hơn ở fool."),
	("pull", "pool", "/ʊ/ ngắn và /uː/ dài."),
	("live", "leave", "/ɪ/ ngắn và /iː/ dài; âm cuối /v/ phải rung môi-răng."),
	("sit", "seat", "/ɪ/ ngắn và /iː/ dài."),
	("think", "sink", "/θ/ đặt lưỡi giữa răng, /s/ thì không."),
	("three", "tree", "/θ/ đặt lưỡi giữa răng; tree bắt đầu bằng /t/."),
	("thin", "tin", "/θ/ thổi hơi qua lưỡi; /t/ bật hơi."),
	("then", "den", "/ð/ lưỡi giữa răng có rung thanh; /d/ lưỡi chạm lợi."),
	("bad", "bed", "/æ/ há miệng rộng hơn /e/."),
	("cat", "cut", "/æ/ há rộng; /ʌ/ ngắn, miệng mở vừa."),
	("light", "right", "/l/ đầu lưỡi chạm lợi; /r/ cuộn lưỡi, không chạm."),
	("seat", "seed", "Âm cuối /t/ vô thanh và /d/ hữu thanh; nguyên âm trước /d/ dài hơn."),
	("rice", "rise", "Âm cuối /s/ vô thanh và /z/ hữu thanh."),
	("west", "vest", "/w/ tròn môi, không chạm răng; /v/ răng trên chạm môi dưới."),
	("back", "bag", "Âm cuối /k/ vô thanh và /g/ hữu thanh."),
	("bet", "bat", "/e/ và /æ/: miệng mở rộng dần."),
]

SILENT_PROMPTS = [
	"Describe what you did this morning.",
	"Introduce your family in a few sentences.",
	"What do you usually eat for lunch? Why?",
	"Talk about a place you would like to visit.",
	"Describe your best friend.",
	"What do you do in your free time?",
	"Explain how to get from your home to school or work.",
	"What is your favourite season and why?",
]


def sentence_list() -> list[dict]:
	return [{"id": sid, "focus": focus, "text": text, "tip_vi": FOCUS_TIPS[focus]} for sid, focus, text in SENTENCES]


def sentence_text(sentence_id: str) -> str:
	if sentence_id not in _BY_ID:
		raise ValueError("sentence_not_found")
	return _BY_ID[sentence_id][1]


def word_tips(word: str) -> list[str]:
	"""Mẹo cho một từ phát âm yếu, theo hình dạng chữ (luật cố định, chỉ gợi ý)."""
	w = re.sub(r"[^a-z]", "", word.lower())
	tips = []
	if "th" in w:
		tips.append("th")
	if re.search(r"ed$", w):
		tips.append("ed")
	elif re.search(r"[^aeiou]{2,}$|[ptkdsz]$", w):
		tips.append("final")
	if re.match(r"(str|spr|spl|scr|sk|sp|st|[bcdfgptk][lr])", w):
		tips.append("cluster")
	if len(re.findall(r"[aeiouy]+", w)) >= 3:
		tips.append("stress")
	return tips


def build_feedback(words: list[tuple[str, float]], focus: str) -> list[dict]:
	"""Từ yếu (< 75) kèm mẹo tiếng Việt; nếu không từ nào gắn được mẹo thì dùng mẹo của trọng tâm câu."""
	out = []
	for word, score in words:
		if score >= 75:
			continue
		keys = word_tips(word) or [focus]
		out.append({"word": word, "score": round(score), "tips_vi": [FOCUS_TIPS[k] for k in keys]})
	return out


async def assess(db: AsyncSession, user_id: uuid.UUID, sentence_id: str, audio: UploadFile) -> dict:
	text = sentence_text(sentence_id)
	extension = Path(audio.filename or "").suffix.lower()
	if extension not in _ALLOWED_EXTENSIONS:
		raise ValueError("unsupported_audio_type")
	content = await audio.read()
	if not content:
		raise ValueError("empty_audio")
	path = speaking_service._audio_dir() / f"pron_{uuid.uuid4()}{extension}"
	path.write_bytes(content)
	try:
		result = await run_in_threadpool(speech_service.assess_pronunciation, str(path), "en-US", text)
	except speech_service.SpeechServiceError as error:
		raise ValueError("pronunciation_service_unavailable") from error
	finally:
		path.unlink(missing_ok=True)  # chỉ cần điểm; không giữ lại giọng người học
	await award_activity(db, user_id, "pronunciation_practice", score=result.score)
	await db.commit()
	return {
		"sentence_id": sentence_id,
		"score": round(result.score, 1),
		"accuracy": round(result.accuracy, 1),
		"fluency": round(result.fluency, 1),
		"completeness": round(result.completeness, 1),
		"words": [{"word": w, "score": round(s)} for w, s in result.words],
		"weak_words": build_feedback(result.words, _BY_ID[sentence_id][0]),
	}


def sentence_audio(sentence_id: str) -> bytes:
	return speech_service.synthesize_azure_speech(sentence_text(sentence_id))


# --- Cặp âm dễ nhầm (4.2) ---
def pairs_quiz(count: int) -> list[dict]:
	picks = random.sample(range(len(PAIRS)), min(count, len(PAIRS)))
	out = []
	for i in picks:
		a, b, _ = PAIRS[i]
		which = random.randint(0, 1)
		# id mã hóa (cặp, từ được đọc); client chỉ cần gửi lại id + từ đã chọn.
		out.append({"id": f"{i}-{which}", "options": [a, b], "speak": (a, b)[which]})
	return out


def pairs_check(answers: list[dict]) -> dict:
	results = []
	for item in answers:
		try:
			idx, which = (int(x) for x in item["id"].split("-"))
			a, b, note = PAIRS[idx]
			correct = (a, b)[which]
		except (ValueError, IndexError) as error:
			raise ValueError("invalid_pair_id") from error
		results.append(
			{
				"id": item["id"],
				"correct_word": correct,
				"chosen": item["choice"],
				"is_correct": item["choice"].strip().lower() == correct,
				"pair": [a, b],
				"note_vi": note,
			}
		)
	right = sum(r["is_correct"] for r in results)
	return {"correct": right, "total": len(results), "results": results}


# --- Nói thầm (4.5) ---
def silent_prompt() -> dict:
	i = random.randrange(len(SILENT_PROMPTS))
	return {"id": i, "prompt": SILENT_PROMPTS[i]}


async def silent_answer(db: AsyncSession, user_id: uuid.UUID, prompt_id: int, text: str) -> dict:
	if not 0 <= prompt_id < len(SILENT_PROMPTS):
		raise ValueError("prompt_not_found")
	words = re.findall(r"[A-Za-z']+", text)
	# ponytail: chỉ kiểm độ dài/đa dạng, không chấm nội dung; thêm LLM chấm ngữ pháp nếu cần.
	if len(words) < 8 or len({w.lower() for w in words}) < 5:
		raise ValueError("answer_too_short")
	try:
		if not await llm_service.judge_silent_answer(SILENT_PROMPTS[prompt_id], text):
			raise ValueError("answer_off_topic")
	except llm_service.AIServiceError:
		pass  # ponytail: model chấm lỗi/không chạy thì cho qua (không chặn người học vì lỗi hạ tầng)
	# Quá SILENT_XP_DAILY_CAP lần/ngày vẫn giữ streak nhưng không cộng XP (chống cày XP bằng gõ bừa).
	done_today = await db.scalar(
		select(func.count()).select_from(ActivityLog).where(
			ActivityLog.user_id == user_id, ActivityLog.activity == "speaking_silent", ActivityLog.created_at >= day_start()
		)
	)
	xp = XP_BY_ACTIVITY["speaking_silent"] if done_today < SILENT_XP_DAILY_CAP else 0
	await award_activity(db, user_id, "speaking_silent", xp=xp)
	await db.commit()
	return {"words": len(words), "xp": xp}
