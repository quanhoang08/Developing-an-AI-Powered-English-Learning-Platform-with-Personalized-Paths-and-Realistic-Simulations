# Business logic ôn từ vựng bằng ngữ cảnh: Contextual Guessing (điền từ vào câu) và Custom Story
# (truyện AI từ từ đã lưu). Bảng contextual_guess_attempts/custom_stories đã có sẵn trong DB.
import random
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vocab import ContextualGuessAttempt, CustomStory, VocabItem
from app.services import llm_service


async def create_guess_attempt(
	db: AsyncSession, user_id: uuid.UUID, vocab_item_id: uuid.UUID | None, term: str | None
) -> ContextualGuessAttempt:
	# Từ lấy từ vocab_items thì bắt buộc thuộc user (không đoán từ của tài khoản khác);
	# gõ tự do thì dùng thẳng term, không có định nghĩa để gợi ý cho model.
	definition = None
	if vocab_item_id is not None:
		item = await db.scalar(
			select(VocabItem).where(VocabItem.id == vocab_item_id, VocabItem.user_id == user_id)
		)
		if item is None:
			raise ValueError("vocab_not_found")
		term, definition = item.term, item.definition

	challenge = await llm_service.generate_guess_challenge(term, definition)
	# Xáo vị trí đáp án đúng ở đây thay vì tin model (xem generate_guess_challenge).
	options = [term, *challenge["distractors"]]
	random.shuffle(options)

	attempt = ContextualGuessAttempt(
		user_id=user_id,
		vocab_item_id=vocab_item_id,
		term=term,
		challenge_sentence=challenge["challenge_sentence"],
		options=options,
		correct_option_index=options.index(term),
	)
	db.add(attempt)
	await db.commit()
	await db.refresh(attempt)
	return attempt


async def submit_guess_attempt(
	db: AsyncSession, user_id: uuid.UUID, attempt_id: uuid.UUID, selected_option_index: int
) -> ContextualGuessAttempt:
	attempt = await db.scalar(
		select(ContextualGuessAttempt)
		.where(ContextualGuessAttempt.id == attempt_id, ContextualGuessAttempt.user_id == user_id)
		.with_for_update()
	)
	if attempt is None:
		raise ValueError("attempt_not_found")
	# Mỗi lượt chỉ nộp 1 lần — nếu không, user thử lần lượt 4 đáp án để dò ra đáp án đúng.
	if attempt.selected_option_index is not None:
		raise ValueError("attempt_already_submitted")

	attempt.selected_option_index = selected_option_index
	attempt.is_correct = selected_option_index == attempt.correct_option_index
	await db.commit()
	return attempt


def find_missing_terms(content: str, terms: list[str]) -> list[str]:
	# Khớp theo đầu từ (không phân biệt hoa/thường) để "run" vẫn khớp "running"/"runs".
	return [term for term in terms if not re.search(rf"\b{re.escape(term)}", content, re.IGNORECASE)]


async def create_story(
	db: AsyncSession,
	user_id: uuid.UUID,
	vocab_item_ids: list[uuid.UUID],
	theme: str | None,
	length: str,
) -> tuple[CustomStory, list[str]]:
	unique_ids = list(dict.fromkeys(vocab_item_ids))
	items = (
		await db.scalars(
			select(VocabItem).where(VocabItem.id.in_(unique_ids), VocabItem.user_id == user_id)
		)
	).all()
	# Thiếu bất kỳ id nào (không tồn tại hoặc của user khác) đều coi là không hợp lệ.
	if len(items) != len(unique_ids):
		raise ValueError("vocab_not_found")

	terms = [item.term for item in items]
	content = await llm_service.generate_story(terms, theme, length)
	story = CustomStory(user_id=user_id, vocab_item_ids=unique_ids, generated_text=content)
	db.add(story)
	await db.commit()
	await db.refresh(story)
	return story, find_missing_terms(content, terms)
