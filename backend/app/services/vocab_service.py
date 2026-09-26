# Business logic Vocabulary: tạo từ, liệt kê từ đến hạn ôn, ghi nhận review (SM-2).
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notebook import Document
from app.models.vocab import VocabItem, VocabReview
from app.services.gamification_service import award_activity
from app.services.sm2_service import apply_sm2


async def create_vocab_item(
	db: AsyncSession,
	user_id: uuid.UUID,
	term: str,
	definition: str | None,
	document_id: uuid.UUID | None,
	source_url: str | None,
	ipa: str | None,
	part_of_speech: str | None,
	example_sentence: str | None,
	synonyms: list[str],
	antonyms: list[str],
) -> VocabItem:
	# Document source phải thuộc user hiện tại để không liên kết chéo dữ liệu.
	if document_id is not None:
		document = await db.scalar(
			select(Document).where(Document.id == document_id, Document.user_id == user_id)
		)
		if document is None:
			raise ValueError("document_not_found")

	# Mỗi user chỉ lưu 1 mục cho mỗi từ (không phân biệt hoa/thường) — khớp unique index
	# uq_vocab_items_user_term; kiểm tra trước để trả lỗi rõ ràng thay vì IntegrityError.
	term = term.strip()
	if await db.scalar(
		select(VocabItem.id).where(VocabItem.user_id == user_id, func.lower(VocabItem.term) == term.lower())
	):
		raise ValueError("vocab_duplicate")

	# Vocab item và trạng thái SM-2 được tạo cùng transaction.
	item = VocabItem(
		user_id=user_id,
		term=term,
		definition=definition,
		document_id=document_id,
		source_url=source_url,
		ipa=ipa,
		part_of_speech=part_of_speech,
		example_sentence=example_sentence,
		synonyms=synonyms,
		antonyms=antonyms,
	)
	db.add(item)
	await db.flush()
	db.add(VocabReview(vocab_item_id=item.id, next_review_at=datetime.now(timezone.utc)))
	try:
		await db.commit()
	except IntegrityError as error:
		# 2 request lưu cùng 1 từ đồng thời: cả hai qua bước kiểm tra, unique index chặn request sau.
		await db.rollback()
		raise ValueError("vocab_duplicate") from error
	await db.refresh(item)
	return item


async def list_due_vocab(db: AsyncSession, user_id: uuid.UUID) -> list[VocabItem]:
	# Chỉ trả từ của user hiện tại có lịch review đến hạn.
	result = await db.execute(
		select(VocabItem)
		.join(VocabReview, VocabReview.vocab_item_id == VocabItem.id)
		.where(
			VocabItem.user_id == user_id,
			VocabReview.next_review_at <= datetime.now(timezone.utc),
		)
		.order_by(VocabReview.next_review_at.asc())
	)
	return list(result.scalars().all())


async def review_vocab(
	db: AsyncSession, user_id: uuid.UUID, vocab_item_id: uuid.UUID, quality: int
) -> VocabReview:
	# Join qua VocabItem để ngăn user review từ của tài khoản khác.
	review = await db.scalar(
		select(VocabReview)
		.join(VocabItem, VocabItem.id == VocabReview.vocab_item_id)
		.where(VocabReview.vocab_item_id == vocab_item_id, VocabItem.user_id == user_id)
	)
	if review is None:
		raise ValueError("vocab_not_found")

	# Chỉ ôn thẻ ĐẾN HẠN mới được tính streak/XP: nếu không, bấm review lặp lại một thẻ sẽ
	# cày XP vô hạn. Phải đọc next_review_at trước apply_sm2 vì hàm này dời lịch ôn.
	was_due = review.next_review_at <= datetime.now(timezone.utc)

	# Hàm SM-2 chỉ thay đổi state trong memory; commit ở service đảm bảo transaction.
	apply_sm2(review, quality)
	if was_due:
		# Cộng streak/XP cùng transaction với kết quả review để hai bên luôn khớp.
		await award_activity(db, user_id, "vocab_review")
	await db.commit()
	await db.refresh(review)
	return review
