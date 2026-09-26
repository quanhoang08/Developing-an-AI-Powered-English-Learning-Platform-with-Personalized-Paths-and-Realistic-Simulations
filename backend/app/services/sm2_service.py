# Thuật toán SM-2 (SuperMemo) thuần, không đụng DB — chỉ tính toán lịch spaced repetition.
from datetime import datetime, timedelta, timezone

from app.models.vocab import VocabReview


def apply_sm2(review: VocabReview, quality: int) -> datetime:
	"""Cập nhật một review theo công thức SM-2 và trả next_review_at."""
	# SM-2 giảm ease factor theo chất lượng, nhưng không cho thấp hơn 1.30.
	ease_factor = float(review.ease_factor)
	review.ease_factor = max(
		1.3,
		ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
	)

	# Quality dưới 3 nghĩa là quên; reset chu kỳ và số lần nhớ liên tiếp.
	if quality < 3:
		review.repetitions = 0
		review.interval_days = 1
	else:
		review.repetitions += 1
		if review.repetitions == 1:
			review.interval_days = 1
		elif review.repetitions == 2:
			review.interval_days = 6
		else:
			review.interval_days = round(review.interval_days * review.ease_factor)

	review.last_grade = quality
	review.last_reviewed_at = datetime.now(timezone.utc)
	review.next_review_at = review.last_reviewed_at + timedelta(days=review.interval_days)
	return review.next_review_at
