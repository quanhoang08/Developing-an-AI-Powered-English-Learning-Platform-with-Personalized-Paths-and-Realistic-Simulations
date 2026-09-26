# Rearrange the Block (feature-reading.md mục 6, feature-writing.md mục 4): sắp xếp lại khối câu
# (Reading) hoặc cụm ngữ pháp (Writing) đã bị xáo trộn. Dùng chung quiz_attempts với quiz_id NULL;
# chấm điểm rule-based (không gọi LLM), partial credit = số khối đúng vị trí / tổng số khối.
import random
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import NamedTuple, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.adaptive import QuizAttempt, UserError
from app.models.notebook import DocumentChunk
from app.models.reading import GeneratedPassage, ReadingSession
from app.models.user import User
from app.services import adaptive_service, llm_service

READING = "rearrange_reading"
WRITING = "rearrange_writing"
# Nhóm lỗi làm nguồn ưu tiên cho từng nhánh (api-spec.md phụ lục A).
_ERROR_TYPE = {READING: "reading_comprehension", WRITING: "grammar"}
_MIN_BLOCKS = 3
_MAX_BLOCKS = 6
_MAX_SENTENCE_WORDS = 60
_ERROR_CANDIDATES = 20
_RECENT_READING_SESSIONS = 5
_MAX_LEVEL = 5
# Model local hay trả output hỏng (thiếu chữ, sai JSON) → thử lại vài lần trước khi báo lỗi người học.
_GENERATION_ATTEMPTS = 3

T = TypeVar("T")


async def _retry_bad_output(make: Callable[[], Awaitable[T]]) -> T:
	for attempt in range(_GENERATION_ATTEMPTS):
		try:
			return await make()
		except llm_service.AIServiceError as error:
			if error.code != "ai_bad_output" or attempt == _GENERATION_ATTEMPTS - 1:
				raise
	raise AssertionError("unreachable")  # pragma: no cover


class RearrangeResult(NamedTuple):
	score: float
	correct_order: list[str]
	# "rules": so khớp thứ tự; "ollama": giám khảo LLM local đã xét bài dạng mở (kèm giải thích).
	graded_by: str
	explanation: str | None


def split_sentences(text: str) -> list[str]:
	parts = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
	return [part for part in parts if part]


def paragraph_blocks(text: str) -> list[str] | None:
	"""Tối đa 6 câu đầu của đoạn làm khối; None nếu quá ít câu hoặc có câu quá dài để kéo thả."""
	sentences = split_sentences(text)[:_MAX_BLOCKS]
	if len(sentences) < _MIN_BLOCKS or any(len(s.split()) > _MAX_SENTENCE_WORDS for s in sentences):
		return None
	return sentences


def _letters(text: str) -> str:
	return re.sub(r"[^a-z0-9']", "", text.lower())


def build_grammar_blocks(result: dict, sentence: str | None) -> tuple[list[str], list[list[int]]]:
	"""Kiểm tra output LLM: cụm ghép lại phải đúng bằng câu gốc, thứ tự thay thế phải là hoán vị hợp lệ.

	Không tin model ở đây: cụm sai/thiếu chữ sẽ làm bài không thể giải đúng nên coi là lỗi AI.
	"""
	chunks = [chunk.strip() for chunk in result["chunks"] if chunk.strip()]
	expected = sentence or result["sentence"]
	# So theo chữ, bỏ hoa/thường + dấu câu + khoảng trắng: model 7B thường bỏ dấu chấm cuối câu hoặc
	# tách dấu câu ra thành khối riêng, nhưng vẫn đủ chữ đúng thứ tự thì bài vẫn giải được.
	if not _MIN_BLOCKS <= len(chunks) <= _MAX_BLOCKS or _letters("".join(chunks)) != _letters(expected):
		raise llm_service.AIServiceError("rearrange_blocks_malformed", "ai_bad_output")

	identity = list(range(len(chunks)))
	alternatives: list[list[int]] = []
	for order in result["alternative_orders"]:
		if sorted(order) == identity and order != identity and order not in alternatives:
			alternatives.append(order)
	return chunks, alternatives


def shuffle_order(ids: list[str], accepted_orders: list[list[str]]) -> list[str]:
	# Tránh trả đề đã sẵn ở thứ tự đúng; giới hạn số lần thử phòng khi mọi hoán vị đều được chấp nhận.
	accepted = {tuple(order) for order in accepted_orders}
	order = ids[:]
	for _ in range(20):
		random.shuffle(order)
		if tuple(order) not in accepted:
			break
	return order


def grade_order(submitted: list[str], accepted_orders: list[list[str]]) -> tuple[float, list[str]]:
	"""Partial credit theo thứ tự chấp nhận gần nhất với bài nộp; trả (điểm 0-1, thứ tự đó)."""
	best = max(accepted_orders, key=lambda order: sum(a == b for a, b in zip(submitted, order)))
	matches = sum(a == b for a, b in zip(submitted, best))
	return round(matches / len(best), 2), best


async def _open_source_error_ids(db: AsyncSession, user_id: uuid.UUID, attempt_type: str) -> set[str]:
	# Lỗi đang là nguồn của 1 bài chưa nộp thì không được dùng lại (feature-reading.md mục 6.5).
	payloads = await db.scalars(
		select(QuizAttempt.payload).where(
			QuizAttempt.user_id == user_id,
			QuizAttempt.attempt_type == attempt_type,
			QuizAttempt.answers.is_(None),
		)
	)
	return {p["source_error_id"] for p in payloads if p and p.get("source_error_id")}


async def _pick_error_source(
	db: AsyncSession, user_id: uuid.UUID, attempt_type: str, exclude: set[str]
) -> tuple[UserError, str] | None:
	"""Lỗi gần nhất còn dùng được: có chữ nguồn (corrected_text/original_text) đủ dài để chia khối."""
	errors = await db.scalars(
		select(UserError)
		.where(UserError.user_id == user_id, UserError.error_type == _ERROR_TYPE[attempt_type])
		.order_by(UserError.created_at.desc())
		.limit(_ERROR_CANDIDATES)
	)
	for error in errors:
		detail = error.detail or {}
		text = detail.get("corrected_text") or detail.get("original_text")
		if str(error.id) in exclude or not text:
			continue
		if attempt_type == READING and paragraph_blocks(text):
			return error, text
		if attempt_type == WRITING and 4 <= len(text.split()) <= 30:
			return error, text
	return None


async def _recent_reading_blocks(db: AsyncSession, user_id: uuid.UUID) -> list[str] | None:
	"""Fallback cấp 1: đoạn user đã đọc gần đây (passage Skim & Scan hoặc chunk tài liệu Classic)."""
	sessions = await db.scalars(
		select(ReadingSession)
		.where(ReadingSession.user_id == user_id)
		.order_by(ReadingSession.created_at.desc())
		.limit(_RECENT_READING_SESSIONS)
	)
	for session in sessions:
		if session.generated_passage_id:
			passage = await db.get(GeneratedPassage, session.generated_passage_id)
			blocks = paragraph_blocks(passage.content) if passage else None
			if blocks:
				return blocks
		elif session.document_id:
			chunks = await db.scalars(
				select(DocumentChunk.content)
				.where(DocumentChunk.document_id == session.document_id)
				.order_by(DocumentChunk.chunk_index)
				.limit(30)
			)
			for content in chunks:
				blocks = paragraph_blocks(content)
				if blocks:
					return blocks
	return None


async def _generated_paragraph_blocks(level: str) -> list[str]:
	texts = paragraph_blocks(await llm_service.generate_rearrange_paragraph(level))
	if texts is None:
		raise llm_service.AIServiceError("rearrange_paragraph_malformed", "ai_bad_output")
	return texts


async def _generated_grammar_blocks(sentence: str | None, level: str) -> tuple[list[str], list[list[int]]]:
	return build_grammar_blocks(await llm_service.generate_grammar_blocks(sentence, level), sentence)


async def create_attempt(
	db: AsyncSession, user: User, attempt_type: str
) -> tuple[QuizAttempt, list[dict]]:
	"""Sinh 1 bài Rearrange; trả (attempt, khối đã xáo trộn). Nguồn: user_errors → nội dung đã đọc → LLM."""
	level = user.target_level or "b1"
	exclude = await _open_source_error_ids(db, user.id, attempt_type)
	picked = await _pick_error_source(db, user.id, attempt_type, exclude)
	error = picked[0] if picked else None
	is_open_form = None

	if attempt_type == READING:
		source = "error"
		texts = paragraph_blocks(picked[1]) if picked else None
		if texts is None:
			error, source = None, "content"
			texts = await _recent_reading_blocks(db, user.id)
		if texts is None:
			source = "generated"
			texts = await _retry_bad_output(lambda: _generated_paragraph_blocks(level))
		alternatives: list[list[int]] = []
		is_open_form = False
	else:
		source = "error" if picked else "generated"
		texts, alternatives = await _retry_bad_output(
			lambda: _generated_grammar_blocks(picked[1] if picked else None, level)
		)
		# Chốt dạng mở/đóng tại đây và không bao giờ ghi đè lúc chấm (feature-writing.md mục 4.3).
		is_open_form = bool(alternatives)

	blocks = [{"id": str(uuid.uuid4()), "text": text} for text in texts]
	ids = [block["id"] for block in blocks]
	# Chỉ thứ tự gốc được luật chấp nhận: alternative_orders do model 7B sinh thường vô nghĩa nên chỉ
	# dùng làm gợi ý cờ is_open_form; thứ tự khác được Ollama xét lúc chấm (judge_rearranged_order).
	accepted_orders = [ids]

	attempt = QuizAttempt(
		user_id=user.id,
		attempt_type=attempt_type,
		is_open_form=is_open_form,
		payload={
			"blocks": blocks,
			"accepted_orders": accepted_orders,
			"source_error_id": str(error.id) if error else None,
			"source": source,
		},
	)
	db.add(attempt)
	await db.commit()
	await db.refresh(attempt)

	by_id = {block["id"]: block for block in blocks}
	return attempt, [by_id[block_id] for block_id in shuffle_order(ids, accepted_orders)]


async def submit_attempt(
	db: AsyncSession,
	user_id: uuid.UUID,
	attempt_id: uuid.UUID,
	block_order: list[str],
	attempt_type: str,
) -> RearrangeResult:
	attempt = await db.scalar(
		select(QuizAttempt)
		.where(
			QuizAttempt.id == attempt_id,
			QuizAttempt.user_id == user_id,
			QuizAttempt.attempt_type == attempt_type,
		)
		.with_for_update()
	)
	if attempt is None:
		raise ValueError("attempt_not_found")
	if attempt.answers is not None:
		raise ValueError("attempt_already_submitted")

	payload = attempt.payload
	if sorted(block_order) != sorted(payload["accepted_orders"][0]):
		raise ValueError("invalid_block_order")

	texts = {block["id"]: block["text"] for block in payload["blocks"]}
	score, correct_order = grade_order(block_order, payload["accepted_orders"])
	graded_by, explanation = "rules", None
	if score < 1:
		# Lệch đáp án chưa chắc là sai (đoạn văn có câu hoán đổi được, câu có thể đảo trạng ngữ) → nhờ
		# Ollama xét mọi bài chưa đạt tuyệt đối. Ollama lỗi thì giữ điểm rule-based, không làm hỏng
		# lượt nộp.
		try:
			agrees = await llm_service.judge_rearranged_order(
				[texts[block_id] for block_id in block_order],
				"reading" if attempt_type == READING else "writing",
			)
		except llm_service.AIServiceError:
			agrees = None
		if agrees is not None:
			graded_by = "ollama"
			if agrees:
				score, correct_order = 1.0, block_order
				explanation = "Ollama read your order and agrees it works just as well."
			else:
				explanation = "Ollama would arrange these pieces differently, so you get partial credit."
	attempt.answers = block_order
	attempt.score = score
	attempt.completed_at = datetime.now(timezone.utc)

	source_error = (
		await db.get(UserError, uuid.UUID(payload["source_error_id"])) if payload["source_error_id"] else None
	)
	if score < 1:
		misplaced = sum(a != b for a, b in zip(block_order, correct_order))
		error = adaptive_service.record_error(
			db,
			user_id,
			_ERROR_TYPE[attempt_type],
			{
				"source": attempt_type,
				"corrected_text": " ".join(texts[block_id] for block_id in payload["accepted_orders"][0]),
				"explanation": f"{misplaced}/{len(correct_order)} blocks out of place",
			},
		)
		error.quiz_attempt_id = attempt.id
	elif source_error is not None and source_error.user_id == user_id:
		# Sắp đúng hoàn toàn bài lấy từ lỗi cũ → xem như đã ôn được lỗi đó (như Adaptive quiz).
		source_error.spaced_repetition_level = min((source_error.spaced_repetition_level or 0) + 1, _MAX_LEVEL)

	await db.commit()
	return RearrangeResult(score, correct_order, graded_by, explanation)
