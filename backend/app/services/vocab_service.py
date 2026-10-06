# Business logic Vocabulary: tạo từ, liệt kê từ đến hạn ôn, ghi nhận review (SM-2).
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.adaptive import UserError
from app.models.notebook import Document
from app.models.vocab import VocabItem, VocabReview
from app.models.writing import WritingInsight, WritingSubmission
from app.services import adaptive_service, llm_service, reading_service, vocab_practice_service
from app.services.gamification_service import award_activity
from app.services.sm2_service import apply_sm2

_PHRASE = re.compile(r"[a-z][a-z'-]*( [a-z][a-z'-]*)*")  # chỉ chữ cái tiếng Anh, cách nhau bằng dấu cách
_MAX_PHRASE_WORDS = 4


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
	unit_label: str | None = None,
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
		unit_label=unit_label,
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


async def import_from_errors(db: AsyncSession, user_id: uuid.UUID, limit: int) -> list[VocabItem]:
	"""Biến lỗi từ vựng thành thẻ vocab vào lịch SM-2. Nguồn:
	- Dictation: từ nghe sai (`original_text`, 1 từ lẻ);
	- Speaking dịch từng chữ: cách nói tự nhiên (`corrected_text`) khi chỉ là một cụm ngắn;
	- Writing: gợi ý từ vựng (`suggested_text`) khi chỉ là một cụm ngắn.
	Câu dài (> _MAX_PHRASE_WORDS từ) bị bỏ vì không đem làm thẻ từ được."""
	dictation = await db.scalars(
		select(UserError.detail["original_text"].astext)
		.where(
			UserError.user_id == user_id,
			UserError.error_type.in_(("vocabulary", "spelling")),
			UserError.detail["source"].astext == "dictation",
		)
		.order_by(UserError.created_at.desc())
		.limit(200)
	)
	speaking = await db.scalars(
		select(UserError.detail["corrected_text"].astext)
		.where(UserError.user_id == user_id, UserError.detail["source"].astext == "speaking_literal_translation")
		.order_by(UserError.created_at.desc())
		.limit(200)
	)
	writing = await db.scalars(
		select(WritingInsight.suggested_text)
		.join(WritingSubmission, WritingSubmission.id == WritingInsight.writing_submission_id)
		.where(WritingSubmission.user_id == user_id, WritingInsight.insight_type == "vocabulary")
		.order_by(WritingInsight.created_at.desc())
		.limit(200)
	)
	known = {t.lower() for t in await db.scalars(select(VocabItem.term).where(VocabItem.user_id == user_id))}
	created: list[VocabItem] = []
	candidates = [*dictation, *speaking, *writing]
	for word in dict.fromkeys(" ".join(w.lower().split()) for w in candidates if w):
		if len(created) >= limit:
			break
		if not _PHRASE.fullmatch(word) or len(word.split()) > _MAX_PHRASE_WORDS or word in known:
			continue
		try:
			info = await reading_service.lookup_term(word, f"The expression \"{word}\" came up while the learner was practising English.")
			item = await create_vocab_item(
				db, user_id, word, info["definition"], None, None, info["ipa"], None,
				info["example_sentence"] or None, info["synonyms"], info["antonyms"],
			)
		except (llm_service.AIServiceError, ValueError):
			# Tra từ lỗi hoặc trùng đồng thời: bỏ từ này, các từ còn lại vẫn được thêm.
			continue
		created.append(item)
	return created


async def get_word_family(db: AsyncSession, user_id: uuid.UUID, vocab_item_id: uuid.UUID) -> dict:
	item = await db.scalar(
		select(VocabItem).where(VocabItem.id == vocab_item_id, VocabItem.user_id == user_id)
	)
	if item is None:
		raise ValueError("vocab_not_found")
	return await llm_service.generate_word_family(item.term)


async def check_vocab_sentence(
	db: AsyncSession, user_id: uuid.UUID, vocab_item_id: uuid.UUID, sentence: str
) -> dict:
	"""Chấm câu người học đặt với từ đã lưu; câu sai ngữ pháp được ghi vào user_errors."""
	item = await db.scalar(
		select(VocabItem).where(VocabItem.id == vocab_item_id, VocabItem.user_id == user_id)
	)
	if item is None:
		raise ValueError("vocab_not_found")
	sentence = sentence.strip()
	# Kiểm tra từ có trong câu trước khi gọi LLM: tiết kiệm lượt gọi và khỏi để model chấm câu lạc đề.
	if vocab_practice_service.find_missing_terms(sentence, [item.term]):
		raise ValueError("term_not_used")

	verdict = await llm_service.judge_vocab_sentence(item.term, sentence)
	# Model local đôi khi cắt cụt nhận xét: thay bằng câu chung còn hơn hiển thị nửa câu.
	if len(verdict["feedback_vi"].strip()) < 15:
		verdict["feedback_vi"] = "Câu đúng." if verdict["grammar_ok"] else "Câu cần sửa như gợi ý."
	if not verdict["grammar_ok"]:
		adaptive_service.record_error(
			db,
			user_id,
			"grammar",
			{
				"source": "vocab_sentence",
				"original_text": sentence,
				"corrected_text": verdict["corrected_sentence"],
				"explanation": verdict["feedback_vi"],
			},
		)
		await db.commit()
	return verdict


_UNIT_SEP = re.compile(r"\t| [-–—] |\s*[:=]\s*")
_MAX_UNIT_LOOKUPS = 5  # mỗi từ thiếu nghĩa tốn 1 lần tra Ollama


def parse_unit_line(line: str) -> tuple[str, str | None]:
	"""'term - nghĩa' / 'term: nghĩa' / 'term<tab>nghĩa' / 'term' -> (term, nghĩa hoặc None)."""
	parts = _UNIT_SEP.split(line.strip(), maxsplit=1)
	return parts[0].strip(), (parts[1].strip() if len(parts) > 1 and parts[1].strip() else None)


async def import_unit(db: AsyncSession, user_id: uuid.UUID, lines: list[str], unit_label: str | None = None) -> dict:
	"""Nhập hàng loạt từ của một unit sách giáo khoa vào vocab + lịch SM-2 (backlog 3.11).

	Dòng có sẵn nghĩa thì lưu thẳng (không LLM); dòng chỉ có từ thì tra Ollama, tối đa
	_MAX_UNIT_LOOKUPS từ mỗi lần, phần còn lại trả về `skipped_no_definition` để gửi lại.
	"""
	created: list[VocabItem] = []
	duplicates: list[str] = []
	pending: list[str] = []
	invalid: list[str] = []
	lookups = 0
	seen: set[str] = set()
	for line in lines:
		term, definition = parse_unit_line(line)
		key = term.lower()
		if not re.fullmatch(r"[A-Za-z][A-Za-z' .-]{0,99}", term):
			if line.strip():
				invalid.append(line.strip()[:100])
			continue
		if key in seen:
			continue
		seen.add(key)
		info: dict = {"ipa": None, "example_sentence": None, "synonyms": [], "antonyms": []}
		if definition is None:
			if lookups >= _MAX_UNIT_LOOKUPS:
				pending.append(term)
				continue
			lookups += 1
			try:
				info = await reading_service.lookup_term(term, f'The word "{term}" is from a textbook vocabulary list.')
			except llm_service.AIServiceError:
				pending.append(term)
				continue
			definition = info["definition"]
			info["example_sentence"] = info["example_sentence"] or None
		try:
			created.append(
				await create_vocab_item(
					db, user_id, term, definition[:1000], None, None, info["ipa"], None,
					info["example_sentence"], info["synonyms"], info["antonyms"], unit_label,
				)
			)
		except ValueError:
			duplicates.append(term)
	return {"created": created, "duplicates": duplicates, "skipped_no_definition": pending, "invalid": invalid}


async def list_units(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
	"""Các unit người học đã nhập kèm số từ (không tính từ không thuộc unit nào)."""
	rows = await db.execute(
		select(VocabItem.unit_label, func.count())
		.where(VocabItem.user_id == user_id, VocabItem.unit_label.is_not(None))
		.group_by(VocabItem.unit_label)
		.order_by(VocabItem.unit_label)
	)
	return [{"unit": unit, "count": count} for unit, count in rows.all()]


async def list_unit_words(db: AsyncSession, user_id: uuid.UUID, unit_label: str) -> list[VocabItem]:
	return list(
		await db.scalars(
			select(VocabItem).where(VocabItem.user_id == user_id, VocabItem.unit_label == unit_label).order_by(VocabItem.term)
		)
	)
