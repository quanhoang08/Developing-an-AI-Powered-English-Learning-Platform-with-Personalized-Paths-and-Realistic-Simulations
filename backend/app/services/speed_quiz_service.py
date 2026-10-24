"""1v1 Speed Quiz (tài liệu tính năng V.4): ghép 2 người online, cùng 5 câu từ vựng, ai đúng nhiều hơn thắng.

Bộ nhớ trong 1 process (không Redis/Socket.io): hàng chờ 1 người + các trận đang chạy.
ponytail: chỉ chạy đúng với 1 worker uvicorn (hiện tại); nhiều worker thì cần Redis pub/sub để ghép cặp.
"""

import asyncio
import random
import uuid
from dataclasses import dataclass, field

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import func, select

from app.core.security import decode_access_token
from app.database import get_session_factory
from app.models.gamification import ActivityLog
from app.services import games_service, wordlist_service
from app.services.gamification_service import award_activity, day_start

QUESTION_COUNT = 5
WIN_XP, PLAY_XP = 12, 6


@dataclass
class Player:
	ws: WebSocket
	user_id: uuid.UUID
	score: int = 0
	answered: set[int] = field(default_factory=set)


@dataclass
class Match:
	players: list[Player]
	questions: list[dict]  # {prompt, options, answer}
	finished: bool = False

	def opponent(self, player: Player) -> Player:
		return self.players[1] if self.players[0] is player else self.players[0]


_waiting: Player | None = None
_lock = asyncio.Lock()
_matches: dict[uuid.UUID, Match] = {}  # user_id -> trận đang chơi


def make_questions(count: int = QUESTION_COUNT) -> list[dict]:
	pool = [w for t in wordlist_service._topics().values() for w in t["words"]]
	questions = []
	for term, meaning, *_ in random.sample(pool, count):
		wrong = random.sample([m for _, m, *_ in pool if m != meaning], 3)
		options = wrong + [meaning]
		random.shuffle(options)
		questions.append({"prompt": term, "options": options, "answer": meaning})
	return questions


def public_questions(match: Match) -> list[dict]:
	return [{"prompt": q["prompt"], "options": q["options"]} for q in match.questions]


async def _award(user_id: uuid.UUID, won: bool) -> int:
	"""XP 1 trận: thắng 12, còn lại 6; chỉ 3 trận đầu mỗi ngày có XP."""
	async with get_session_factory()() as db:
		done = await db.scalar(
			select(func.count()).select_from(ActivityLog).where(
				ActivityLog.user_id == user_id,
				ActivityLog.activity == "speed_quiz_completed",
				ActivityLog.created_at >= day_start(),
			)
		)
		xp = (WIN_XP if won else PLAY_XP) if (done or 0) < games_service.MEMORY_XP_DAILY_CAP else 0
		await award_activity(db, user_id, "speed_quiz_completed", xp=xp)
		await db.commit()
		return xp


async def _send(player: Player, message: dict) -> None:
	try:
		await player.ws.send_json(message)
	except Exception:  # noqa: BLE001 - đối thủ đã rớt kết nối; việc dọn nằm ở vòng nhận của họ
		pass


async def _finish(match: Match, forfeit_by: Player | None = None) -> None:
	if match.finished:
		return
	match.finished = True
	for p in match.players:
		_matches.pop(p.user_id, None)
	a, b = match.players
	for p in match.players:
		if forfeit_by is p:
			continue
		other = match.opponent(p)
		won = forfeit_by is other or (forfeit_by is None and p.score > other.score)
		draw = forfeit_by is None and a.score == b.score
		xp = await _award(p.user_id, won)
		await _send(
			p,
			{"type": "result", "result": "draw" if draw else "win" if won else "lose", "you": p.score, "opponent": other.score, "forfeit": forfeit_by is other, "xp_awarded": xp},
		)


def _user_id(token: str) -> uuid.UUID | None:
	subject = decode_access_token(token)
	try:
		return uuid.UUID(subject) if subject else None
	except ValueError:
		return None


async def handle(ws: WebSocket, token: str) -> None:
	global _waiting
	user_id = _user_id(token)
	if user_id is None:
		await ws.close(code=4401)
		return
	await ws.accept()
	me = Player(ws=ws, user_id=user_id)
	async with _lock:
		if user_id in _matches or (_waiting is not None and _waiting.user_id == user_id):
			await ws.send_json({"type": "error", "code": "already_in_queue"})
			await ws.close()
			return
		other, _waiting = (_waiting, None) if _waiting is not None else (None, me)
		if other is not None:
			match = Match(players=[other, me], questions=make_questions())
			_matches[other.user_id] = _matches[me.user_id] = match
	if other is None:
		await _send(me, {"type": "waiting"})
	else:
		for p in match.players:
			await _send(p, {"type": "start", "questions": public_questions(match)})
	try:
		while True:
			data = await ws.receive_json()
			match = _matches.get(user_id)
			if match is None or data.get("type") != "answer":
				continue
			q = data.get("q")
			if not isinstance(q, int) or not 0 <= q < len(match.questions) or q in me.answered:
				continue
			me.answered.add(q)
			correct = data.get("choice") == match.questions[q]["answer"]
			me.score += int(correct)
			await _send(me, {"type": "feedback", "q": q, "correct": correct, "answer": match.questions[q]["answer"]})
			await _send(match.opponent(me), {"type": "opponent_progress", "answered": len(me.answered), "score": me.score})
			if all(len(p.answered) == len(match.questions) for p in match.players):
				await _finish(match)
	except WebSocketDisconnect:
		pass
	finally:
		async with _lock:
			if _waiting is me:
				_waiting = None
		match = _matches.get(user_id)
		if match is not None and not match.finished:
			await _send(match.opponent(me), {"type": "opponent_left"})
			await _finish(match, forfeit_by=me)
