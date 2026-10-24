"""Mini-game + nhiệm vụ ngày (tài liệu tính năng mục V.1 Daily Wordle / Flip Memory Match, mục VIII Daily Quests).

Không bảng mới: XP và "đã làm hôm nay" đọc từ activity_log (gamification_service.award_activity ghi
cùng transaction). Nhiệm vụ ngày là số đếm theo activity_log của hôm nay; nhận thưởng ghi 1 dòng
activity_log tên `quest:<id>` nên mỗi nhiệm vụ nhận tối đa 1 lần/ngày.
"""

import hashlib
import random
import re
import uuid
from functools import lru_cache

import wordfreq
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gamification import ActivityLog
from app.services.gamification_service import XP_BY_ACTIVITY, award_activity, day_start, study_today

WORDLE_LENGTH = 5
WORDLE_MAX_GUESSES = 6
_ANSWER_POOL = 1500  # 1500 từ 5 chữ phổ biến nhất làm đáp án; đoán thì chấp nhận cả ~10k từ thật
MEMORY_MIN_PAIRS = 4
MEMORY_XP_DAILY_CAP = 3

GAME_ACTIVITIES = tuple(
	f"{g}_completed"
	for g in ("wordle", "memory_match", "word_rain", "bubble_pop", "word_search", "voice_runner", "dictation_racer", "word_chain", "grammar_detective", "speed_quiz")
)

# id -> (tiêu đề, hoạt động tính vào, mục tiêu, XP thưởng thêm)
QUESTS: dict[str, tuple[str, tuple[str, ...], int, int]] = {
	"review_words": ("Review 5 vocabulary cards", ("vocab_review",), 5, 10),
	"speak_once": (
		"Practice speaking once",
		("speaking_turn", "pronunciation_practice", "speaking_silent", "live_call"),
		1,
		10,
	),
	"read_or_listen": (
		"Finish a reading or listening exercise",
		("reading_completed", "dictation_completed", "listening_quiz_completed"),
		1,
		10,
	),
	"play_game": ("Play a mini-game", GAME_ACTIVITIES, 1, 10),
}


@lru_cache(maxsize=1)
def _words() -> tuple[tuple[str, ...], frozenset[str]]:
	pool = [w for w in wordfreq.top_n_list("en", 40000) if len(w) == WORDLE_LENGTH and w.isascii() and w.isalpha()]
	return tuple(sorted(pool[:_ANSWER_POOL])), frozenset(pool[:10000])


def daily_word(day) -> str:
	answers, _ = _words()
	digest = hashlib.sha256(f"lumina-wordle-{day.isoformat()}".encode()).digest()
	return answers[int.from_bytes(digest[:4], "big") % len(answers)]


def is_valid_guess(guess: str) -> bool:
	return guess in _words()[1]


def evaluate(guess: str, answer: str) -> list[str]:
	"""correct/present/absent từng chữ; chữ lặp chỉ tô "present" tối đa bằng số lần chữ đó còn lại trong đáp án."""
	result = ["absent"] * len(guess)
	left: dict[str, int] = {}
	for i, (g, a) in enumerate(zip(guess, answer)):
		if g == a:
			result[i] = "correct"
		else:
			left[a] = left.get(a, 0) + 1
	for i, g in enumerate(guess):
		if result[i] == "absent" and left.get(g, 0) > 0:
			result[i] = "present"
			left[g] -= 1
	return result


async def _today_counts(db: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
	rows = await db.execute(
		select(ActivityLog.activity, func.count())
		.where(ActivityLog.user_id == user_id, ActivityLog.created_at >= day_start())
		.group_by(ActivityLog.activity)
	)
	return dict(rows.all())


async def wordle_status(db: AsyncSession, user_id: uuid.UUID) -> dict:
	counts = await _today_counts(db, user_id)
	return {"length": WORDLE_LENGTH, "max_guesses": WORDLE_MAX_GUESSES, "solved_today": counts.get("wordle_completed", 0) > 0}


async def wordle_guess(db: AsyncSession, user_id: uuid.UUID, guess: str, attempt: int) -> dict:
	"""`attempt` (1-6) do client đếm: đáp án chỉ lộ khi đoán đúng hoặc hết lượt (ponytail: tin client, chỉ ảnh hưởng chính họ)."""
	guess = guess.strip().lower()
	if len(guess) != WORDLE_LENGTH or not is_valid_guess(guess):
		raise ValueError("not_in_word_list")
	answer = daily_word(study_today())
	pattern = evaluate(guess, answer)
	solved = guess == answer
	finished = solved or attempt >= WORDLE_MAX_GUESSES
	xp = 0
	if solved and not (await _today_counts(db, user_id)).get("wordle_completed"):
		xp = XP_BY_ACTIVITY["wordle_completed"]
		await award_activity(db, user_id, "wordle_completed")
		await db.commit()
	return {"pattern": pattern, "solved": solved, "answer": answer if finished else None, "xp_awarded": xp}


async def _complete(db: AsyncSession, user_id: uuid.UUID, game: str) -> dict:
	"""Ghi 1 ván xong: XP chỉ cho MEMORY_XP_DAILY_CAP ván đầu mỗi ngày mỗi game, sau đó vẫn tính là hoạt động (xp 0)."""
	activity = f"{game}_completed"
	done = (await _today_counts(db, user_id)).get(activity, 0)
	xp = XP_BY_ACTIVITY[activity] if done < MEMORY_XP_DAILY_CAP else 0
	await award_activity(db, user_id, activity, xp=xp)
	await db.commit()
	return {"xp_awarded": xp}


async def memory_match_complete(db: AsyncSession, user_id: uuid.UUID, pairs: int, moves: int) -> dict:
	if pairs < MEMORY_MIN_PAIRS or moves < pairs:
		raise ValueError("invalid_game")
	return await _complete(db, user_id, "memory_match")


# Game chỉ cần client báo "đạt điểm tối thiểu": ponytail: tin client (chỉ ảnh hưởng XP của chính họ, có cap/ngày).
SCORE_GAMES = {"word_rain": 5, "bubble_pop": 6, "word_search": 4, "voice_runner": 3, "dictation_racer": 4, "word_chain": 6}


async def score_game_complete(db: AsyncSession, user_id: uuid.UUID, game: str, score: int) -> dict:
	if game not in SCORE_GAMES:
		raise LookupError("game_not_found")
	if score < SCORE_GAMES[game]:
		raise ValueError("score_too_low")
	return await _complete(db, user_id, game)


# ---- Word Chain: nối từ với máy, server kiểm từ hợp lệ + chọn từ đáp lại ----


@lru_cache(maxsize=1)
def _chain_words() -> tuple[str, ...]:
	return tuple(w for w in wordfreq.top_n_list("en", 20000) if 3 <= len(w) <= 9 and w.isascii() and w.isalpha())


def word_chain_turn(chain: list[str], word: str) -> dict:
	"""`chain` = các từ đã dùng (cả hai bên). Trả từ máy đáp lại (None nếu máy bí = người chơi thắng)."""
	word = word.strip().lower()
	if word not in _chain_words_set():
		raise ValueError("not_in_word_list")
	if chain and word[0] != chain[-1][-1]:
		raise ValueError("wrong_start_letter")
	if word in chain:
		raise ValueError("already_used")
	used = {*chain, word}
	options = [w for w in _chain_words() if w[0] == word[-1] and w not in used][:8]
	return {"reply": random.choice(options) if options else None}


@lru_cache(maxsize=1)
def _chain_words_set() -> frozenset[str]:
	return frozenset(_chain_words())


# ---- Grammar Detective: bài đọc có lỗi ẩn, click từ sai; server giữ đáp án ----
# Cú pháp [sai->đúng] đánh dấu từ lỗi.
_PASSAGES = [
	"Yesterday I [go->went] to the market with my sister. We [buyed->bought] some fresh fruit and then we [was->were] very tired.",
	"My brother [don't->doesn't] like coffee, so he usually drinks tea. He [have->has] two cups every morning before work.",
	"There [is->are] many students in the library today. They [studys->study] for the exam that [begin->begins] next week.",
	"She is [more tall->taller] than her mother. Last summer she [have->had] a job at a small cafe and [earn->earned] a lot of money.",
	"I [am agree->agree] with your opinion. The film [what->that] we watched yesterday was interesting and funny.",
	"He [suggested me->suggested that I] take a break. After lunch we [walk->walked] along the river and [talks->talked] about our plans.",
]
_ERR_RE = re.compile(r"^\[(.+)->(.+)\](\W*)$")


def _parse_passage(index: int) -> tuple[list[str], dict[int, str]]:
	"""Trả (token hiển thị, {vị trí token: dạng đúng}); cụm sai nhiều từ gộp thành 1 token (dấu cách trong cụm tạm thay bằng ~ vì str.split() cũng tách cả nbsp)."""
	text = re.sub(r"\[([^\]]+)->([^\]]+)\]", lambda m: "[" + m.group(1).replace(" ", "~") + "->" + m.group(2).replace(" ", "~") + "]", _PASSAGES[index])
	tokens, answers = [], {}
	for raw in text.split():
		m = _ERR_RE.match(raw)
		if m:
			answers[len(tokens)] = m.group(2).replace("~", " ")
			tokens.append(m.group(1).replace("~", " ") + m.group(3))
		else:
			tokens.append(raw)
	return tokens, answers


def detective_new(exclude: int | None = None) -> dict:
	index = random.choice([i for i in range(len(_PASSAGES)) if i != exclude])
	tokens, answers = _parse_passage(index)
	return {"passage_id": index, "tokens": tokens, "error_count": len(answers)}


async def detective_check(db: AsyncSession, user_id: uuid.UUID, passage_id: int, picks: list[int]) -> dict:
	if not 0 <= passage_id < len(_PASSAGES):
		raise LookupError("passage_not_found")
	tokens, answers = _parse_passage(passage_id)
	picked = set(picks)
	found = len(picked & answers.keys())
	false_positives = len(picked - answers.keys())
	passed = found >= -(-len(answers) * 6 // 10) and false_positives <= 1  # >= 60% lỗi, tối đa 1 chọn nhầm
	result = {
		"found": found,
		"total": len(answers),
		"false_positives": false_positives,
		"answers": [{"index": i, "wrong": tokens[i], "correct": c} for i, c in sorted(answers.items())],
		"xp_awarded": 0,
	}
	if passed:
		result["xp_awarded"] = (await _complete(db, user_id, "grammar_detective"))["xp_awarded"]
	return result


async def list_quests(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
	counts = await _today_counts(db, user_id)
	items = []
	for quest_id, (title, activities, target, bonus) in QUESTS.items():
		progress = sum(counts.get(a, 0) for a in activities)
		items.append(
			{
				"id": quest_id,
				"title": title,
				"progress": min(progress, target),
				"target": target,
				"bonus_xp": bonus,
				"claimed": counts.get(f"quest:{quest_id}", 0) > 0,
			}
		)
	return items


async def claim_quest(db: AsyncSession, user_id: uuid.UUID, quest_id: str) -> int:
	quest = next((q for q in await list_quests(db, user_id) if q["id"] == quest_id), None)
	if quest is None:
		raise LookupError("quest_not_found")
	if quest["claimed"] or quest["progress"] < quest["target"]:
		raise ValueError("quest_not_claimable")
	await award_activity(db, user_id, f"quest:{quest_id}", xp=quest["bonus_xp"])
	await db.commit()
	return quest["bonus_xp"]


# ---- Daily Micro-Quiz (extension): 1 câu từ - nghĩa, server giữ đáp án (tra lại theo từ khi chấm) ----
MICRO_QUIZ_XP_DAILY_CAP = 5


def micro_quiz() -> dict:
	from app.services import speed_quiz_service

	question = speed_quiz_service.make_questions(1)[0]
	return {"prompt": question["prompt"], "options": question["options"]}


async def micro_quiz_answer(db: AsyncSession, user_id: uuid.UUID, prompt: str, choice: str) -> dict:
	from app.services import wordlist_service

	meanings = {term.lower(): meaning for t in wordlist_service._topics().values() for term, meaning, *_ in t["words"]}
	answer = meanings.get(prompt.strip().lower())
	if answer is None:
		raise LookupError("question_not_found")
	correct = choice == answer
	xp = 0
	if correct:
		done = (await _today_counts(db, user_id)).get("micro_quiz_completed", 0)
		xp = XP_BY_ACTIVITY["micro_quiz_completed"] if done < MICRO_QUIZ_XP_DAILY_CAP else 0
		await award_activity(db, user_id, "micro_quiz_completed", xp=xp)
		await db.commit()
	return {"correct": correct, "answer": answer, "xp_awarded": xp}
