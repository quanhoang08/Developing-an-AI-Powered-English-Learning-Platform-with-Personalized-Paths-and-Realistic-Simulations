"""Hàng đợi ưu tiên ôn tập: gộp từ vựng đến hạn (vocab_reviews) và lỗi còn yếu (user_errors).

Điểm số là quy ước của đề tài (spec chỉ yêu cầu "sắp theo mức ưu tiên"): điểm cao = nên ôn trước.
Hàm tính điểm là hàm thuần để test độc lập và giải thích được trong báo cáo.
"""

import uuid
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.adaptive import ReviewPriorityItem, UserError
from app.models.vocab import VocabItem, VocabReview

MAX_QUEUE_SIZE = 50
MAX_ERRORS_SCANNED = 500
_RECENCY_WINDOW_DAYS = 14


def error_priority(level: int, created_at: datetime, same_type_count: int, now: datetime) -> float:
	"""Lỗi chưa được ôn (level thấp), mới xảy ra và thuộc loại hay lặp lại thì ưu tiên cao."""
	base = 60 / (1 + max(level, 0))
	age_days = max((now - created_at).total_seconds() / 86400, 0)
	# Lỗi đã ôn đúng ít nhất 1 lần (level > 0) không còn được cộng điểm "mới xảy ra".
	recency = 0.0 if level > 0 else 10 * max(0.0, 1 - age_days / _RECENCY_WINDOW_DAYS)
	frequency = 5 * min(same_type_count, 6)
	return round(base + recency + frequency, 2)


def vocab_priority(overdue_days: float, ease_factor: float) -> float:
	"""Từ đến hạn: trễ hạn càng lâu và ease_factor càng thấp (từ khó nhớ) càng ưu tiên."""
	score = 40 + 2 * min(max(overdue_days, 0), 30) + 10 * (2.5 - ease_factor)
	return round(max(score, 0), 2)


async def rebuild_queue(
	db: AsyncSession, user_id: uuid.UUID, now: datetime | None = None
) -> list[ReviewPriorityItem]:
	"""Tính lại toàn bộ hàng đợi của user (xoá cũ, ghi top MAX_QUEUE_SIZE mới). KHÔNG commit."""
	now = now or datetime.now(timezone.utc)

	errors = (
		await db.scalars(
			select(UserError)
			.where(UserError.user_id == user_id)
			.order_by(UserError.created_at.desc())
			.limit(MAX_ERRORS_SCANNED)
		)
	).all()
	type_counts = Counter(error.error_type for error in errors)

	candidates: list[tuple[str, uuid.UUID, float]] = [
		(
			"error",
			error.id,
			error_priority(error.spaced_repetition_level or 0, error.created_at or now, type_counts[error.error_type], now),
		)
		for error in errors
	]

	due_vocab = await db.execute(
		select(VocabReview.vocab_item_id, VocabReview.next_review_at, VocabReview.ease_factor)
		.join(VocabItem, VocabItem.id == VocabReview.vocab_item_id)
		.where(VocabItem.user_id == user_id, VocabReview.next_review_at <= now)
	)
	for item_id, next_review_at, ease_factor in due_vocab:
		overdue_days = (now - next_review_at).total_seconds() / 86400
		candidates.append(("vocab", item_id, vocab_priority(overdue_days, float(ease_factor or 2.5))))

	top = sorted(candidates, key=lambda candidate: candidate[2], reverse=True)[:MAX_QUEUE_SIZE]

	await db.execute(delete(ReviewPriorityItem).where(ReviewPriorityItem.user_id == user_id))
	rows = [
		ReviewPriorityItem(
			user_id=user_id, item_type=item_type, item_id=item_id, priority_score=score, last_calculated_at=now
		)
		for item_type, item_id, score in top
	]
	db.add_all(rows)
	await db.flush()
	return rows
