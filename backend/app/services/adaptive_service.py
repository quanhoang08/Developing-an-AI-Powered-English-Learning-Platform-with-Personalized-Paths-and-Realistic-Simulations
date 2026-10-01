"""Adaptive Learning Engine: nhật ký lỗi, hàng đợi ôn tập, đề kiểm tra động, thói quen học.

Các module kỹ năng ghi lỗi qua record_error (không commit, cùng transaction với kết quả bài làm);
engine đọc lại để xếp ưu tiên, sinh đề nhắm vào điểm yếu và mô hình hoá thói quen học.
"""

import random
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.adaptive import ERROR_TYPES, Quiz, QuizAttempt, UserError
from app.models.listening import DictationAttempt
from app.models.reading import ReadingSession
from app.models.speaking import ConversationSession, ConversationTurn
from app.models.vocab import VocabItem, VocabReview
from app.models.writing import WritingSubmission
from app.services import llm_service, priority_queue_service
from app.services.gamification_service import award_activity, restore_streak

_MAX_SOURCE_ERRORS = 8
_HABIT_WINDOW_DAYS = 30
_MAX_LEVEL = 5
_FALLBACK_SOURCES = [
	{"id": None, "error_type": "grammar", "detail": {
		"topic": "common grammar: verb tenses, articles, prepositions, subject-verb agreement"}},
	{"id": None, "error_type": "vocabulary", "detail": {
		"topic": "common vocabulary: word choice, collocations, easily confused word pairs"}},
]


def record_error(
	db: AsyncSession, user_id: uuid.UUID, error_type: str, detail: dict | None = None
) -> UserError:
	"""Thêm 1 dòng user_errors vào session (KHÔNG commit). error_type sai là lỗi lập trình → ValueError."""
	if error_type not in ERROR_TYPES:
		raise ValueError(f"unknown_error_type:{error_type}")
	error = UserError(user_id=user_id, error_type=error_type, detail=detail)
	db.add(error)
	return error


async def list_errors(
	db: AsyncSession,
	user_id: uuid.UUID,
	error_type: str | None,
	limit: int,
	offset: int,
	now: datetime | None = None,
) -> list[dict]:
	"""Lỗi của user sắp theo mức ưu tiên giảm dần, kèm điểm ưu tiên."""
	now = now or datetime.now(timezone.utc)
	errors = (
		await db.scalars(
			select(UserError)
			.where(UserError.user_id == user_id)
			.order_by(UserError.created_at.desc())
			.limit(priority_queue_service.MAX_ERRORS_SCANNED)
		)
	).all()
	counts = Counter(error.error_type for error in errors)

	scored = [
		(
			priority_queue_service.error_priority(
				error.spaced_repetition_level or 0, error.created_at or now, counts[error.error_type], now
			),
			error,
		)
		for error in errors
		if error_type is None or error.error_type == error_type
	]
	scored.sort(key=lambda pair: pair[0], reverse=True)
	return [
		{
			"id": error.id,
			"error_type": error.error_type,
			"spaced_repetition_level": error.spaced_repetition_level or 0,
			"detail": error.detail,
			"created_at": error.created_at,
			"priority_score": score,
		}
		for score, error in scored[offset : offset + limit]
	]


async def get_review_queue(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
	"""Tính lại rồi trả hàng đợi ôn tập hiện tại (dữ liệu nguồn thay đổi liên tục nên luôn tính mới)."""
	rows = await priority_queue_service.rebuild_queue(db, user_id)
	await db.commit()

	vocab_ids = [row.item_id for row in rows if row.item_type == "vocab"]
	error_ids = [row.item_id for row in rows if row.item_type == "error"]
	terms: dict[uuid.UUID, str] = {}
	if vocab_ids:
		terms = {item.id: item.term for item in (await db.scalars(select(VocabItem).where(VocabItem.id.in_(vocab_ids)))).all()}
	error_types: dict[uuid.UUID, str] = {}
	if error_ids:
		error_types = {
			error.id: error.error_type
			for error in (await db.scalars(select(UserError).where(UserError.id.in_(error_ids)))).all()
		}
	return [
		{
			"item_type": row.item_type,
			"item_id": row.item_id,
			"priority_score": float(row.priority_score),
			"label": terms.get(row.item_id) if row.item_type == "vocab" else error_types.get(row.item_id),
		}
		for row in rows
	]


async def generate_quiz(
	db: AsyncSession, user_id: uuid.UUID, focus_error_types: list[str] | None, num_questions: int
) -> Quiz:
	"""Sinh đề trắc nghiệm nhắm vào lỗi ưu tiên cao nhất (hoặc theo focus_error_types)."""
	if any(value not in ERROR_TYPES for value in focus_error_types or []):
		raise ValueError("invalid_error_type")

	ranked = await list_errors(db, user_id, None, priority_queue_service.MAX_ERRORS_SCANNED, 0)
	if focus_error_types:
		ranked = [error for error in ranked if error["error_type"] in focus_error_types]
	sources = ranked[:_MAX_SOURCE_ERRORS]
	if not sources:
		# Chưa có lỗi nào (user mới): đề dự phòng theo chủ đề chung, không gắn với user_errors nào.
		sources = [
			source for source in _FALLBACK_SOURCES
			if not focus_error_types or source["error_type"] in focus_error_types
		]
	if not sources:
		raise ValueError("no_errors_to_practice")

	generated = await llm_service.generate_adaptive_quiz(sources, num_questions)

	questions = validate_questions(generated, sources)
	if not questions:
		raise llm_service.AIServiceError("adaptive_quiz_malformed", "ai_bad_output")
	shuffle_options(questions)

	quiz = Quiz(
		user_id=user_id,
		generated_from_error_ids=[source["id"] for source in sources if source["id"] is not None],
		focus_error_types=focus_error_types or sorted({source["error_type"] for source in sources}),
		questions=questions,
	)
	db.add(quiz)
	await db.commit()
	await db.refresh(quiz)
	return quiz


def shuffle_options(questions: list[dict]) -> None:
	"""Model hay đặt đáp án đúng ở cùng 1 vị trí (đo qwen2.5-7b/llama3.2-3b, 13 đề: 59-65% câu ở vị trí B) nên
	người học đoán được không cần đọc. Xáo lại thứ tự lựa chọn tại chỗ và cập nhật correct_option_index theo."""
	for question in questions:
		correct_text = question["options"][question["correct_option_index"]]
		random.shuffle(question["options"])
		question["correct_option_index"] = question["options"].index(correct_text)


def validate_questions(generated: list[dict], sources: list[dict]) -> list[dict]:
	"""Bỏ câu hỏi LLM trả sai cấu trúc (đáp án/chỉ số ngoài phạm vi, tham chiếu lỗi không tồn tại)."""
	valid: list[dict] = []
	for item in generated:
		options = item.get("options") or []
		correct = item.get("correct_option_index")
		source_index = item.get("source_index")
		if len(options) < 2 or not isinstance(correct, int) or not 0 <= correct < len(options):
			continue
		if not isinstance(source_index, int) or not 0 <= source_index < len(sources):
			continue
		source = sources[source_index]
		valid.append(
			{
				"question_text": item["question_text"],
				"options": options,
				"correct_option_index": correct,
				"explanation": item.get("explanation", ""),
				"error_id": str(source["id"]) if source["id"] is not None else None,
				"error_type": source["error_type"],
			}
		)
	return valid


def public_questions(questions: list[dict]) -> list[dict]:
	"""Câu hỏi gửi client trước khi làm bài: giấu đáp án và giải thích."""
	return [
		{"question_text": q["question_text"], "options": q["options"], "error_type": q["error_type"]}
		for q in questions
	]


async def submit_quiz_attempt(
	db: AsyncSession, user_id: uuid.UUID, quiz_id: uuid.UUID, answers: list[int]
) -> dict:
	"""Chấm 1 lượt làm đề: trả kết quả từng câu, tăng level lỗi đã làm đúng, ghi lại lỗi mới khi sai."""
	quiz = await db.scalar(select(Quiz).where(Quiz.id == quiz_id, Quiz.user_id == user_id))
	if quiz is None:
		raise ValueError("quiz_not_found")
	if len(answers) != len(quiz.questions):
		raise ValueError("answer_count_mismatch")

	first_attempt = await db.scalar(select(QuizAttempt.id).where(QuizAttempt.quiz_id == quiz_id).limit(1)) is None

	attempt = QuizAttempt(quiz_id=quiz_id, user_id=user_id, answers=answers)
	db.add(attempt)
	await db.flush()

	results = []
	correct_count = 0
	for question, chosen in zip(quiz.questions, answers):
		is_correct = chosen == question["correct_option_index"]
		correct_count += is_correct
		if is_correct:
			error = await db.get(UserError, uuid.UUID(question["error_id"])) if question["error_id"] else None
			if error is not None and error.user_id == user_id:
				error.spaced_repetition_level = min((error.spaced_repetition_level or 0) + 1, _MAX_LEVEL)
		else:
			db.add(
				UserError(
					user_id=user_id,
					quiz_attempt_id=attempt.id,
					error_type=question["error_type"],
					detail={"source": "adaptive_quiz", "question_text": question["question_text"]},
				)
			)
		results.append(
			{
				"is_correct": is_correct,
				"correct_option_index": question["correct_option_index"],
				"explanation": question.get("explanation", ""),
			}
		)

	attempt.score = round(100 * correct_count / len(quiz.questions), 2)
	# Làm lại cùng 1 đề không cộng thêm XP, tránh cày điểm bằng cách nộp lặp.
	if first_attempt:
		await award_activity(db, user_id, "quiz_completed")
	streak_restored = await restore_streak(db, user_id, len(quiz.questions), float(attempt.score))
	await db.commit()
	return {
		"attempt_id": attempt.id,
		"score": float(attempt.score),
		"results": results,
		"streak_restored": streak_restored,
	}


def summarize_habits(
	events: list[tuple[str, datetime]],
	quiz_scores: list[float],
	now: datetime,
	utc_offset_hours: int,
) -> dict:
	"""Thống kê thói quen từ danh sách (kỹ năng, thời điểm) trong cửa sổ 30 ngày. Hàm thuần.

	quiz_scores sắp mới nhất trước.
	"""
	offset = timedelta(hours=utc_offset_hours)
	local = [(skill, at.astimezone(timezone.utc) + offset) for skill, at in events]
	today = (now.astimezone(timezone.utc) + offset).date()

	active_days = {moment.date() for _, moment in local}
	by_skill = Counter(skill for skill, _ in local)
	hours = Counter(moment.hour for _, moment in local)

	# Tốc độ tiến bộ: điểm trung bình 5 đề gần nhất so với 5 đề trước đó.
	recent, earlier = quiz_scores[:5], quiz_scores[5:10]
	if recent and earlier:
		delta = round(sum(recent) / len(recent) - sum(earlier) / len(earlier), 2)
		trend = "improving" if delta > 2 else "declining" if delta < -2 else "stable"
	else:
		delta, trend = None, "insufficient_data"

	return {
		"window_days": _HABIT_WINDOW_DAYS,
		"active_days": len(active_days),
		"activities_per_active_day": round(len(local) / len(active_days), 2) if active_days else 0.0,
		"studied_today": today in active_days,
		"peak_hour": hours.most_common(1)[0][0] if hours else None,
		"activity_by_skill": dict(by_skill),
		"preferred_skill": by_skill.most_common(1)[0][0] if by_skill else None,
		"quiz_score_change": delta,
		"progress_trend": trend,
	}


async def get_habits(db: AsyncSession, user_id: uuid.UUID, now: datetime | None = None) -> dict:
	now = now or datetime.now(timezone.utc)
	since = now - timedelta(days=_HABIT_WINDOW_DAYS)

	sources = [
		(
			"vocabulary",
			select(VocabReview.last_reviewed_at)
			.join(VocabItem, VocabItem.id == VocabReview.vocab_item_id)
			.where(VocabItem.user_id == user_id, VocabReview.last_reviewed_at >= since),
		),
		(
			"reading",
			select(ReadingSession.completed_at).where(
				ReadingSession.user_id == user_id, ReadingSession.completed_at >= since
			),
		),
		(
			"writing",
			select(WritingSubmission.completed_at).where(
				WritingSubmission.user_id == user_id, WritingSubmission.completed_at >= since
			),
		),
		(
			"listening",
			select(DictationAttempt.created_at).where(
				DictationAttempt.user_id == user_id,
				DictationAttempt.diff_result.is_not(None),
				DictationAttempt.created_at >= since,
			),
		),
		(
			"speaking",
			select(ConversationTurn.created_at)
			.join(ConversationSession, ConversationSession.id == ConversationTurn.conversation_session_id)
			.where(ConversationSession.user_id == user_id, ConversationTurn.created_at >= since),
		),
		(
			"quiz",
			select(QuizAttempt.completed_at).where(QuizAttempt.user_id == user_id, QuizAttempt.completed_at >= since),
		),
	]
	events: list[tuple[str, datetime]] = []
	for skill, query in sources:
		events.extend((skill, moment) for moment in (await db.scalars(query)).all() if moment is not None)

	quiz_scores = [
		float(score)
		for score in (
			await db.scalars(
				select(QuizAttempt.score)
				# quiz_id NOT NULL: chỉ đề Adaptive (thang 0-100); Rearrange chấm thang 0-1 nên loại ra.
				.where(
					QuizAttempt.user_id == user_id,
					QuizAttempt.score.is_not(None),
					QuizAttempt.quiz_id.is_not(None),
				)
				.order_by(QuizAttempt.completed_at.desc())
				.limit(10)
			)
		).all()
	]
	return summarize_habits(events, quiz_scores, now, get_settings().study_utc_offset_hours)
