# Business logic Reading: Classic Mode, Skim & Scan, tra từ, và chấm điểm dùng chung.
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notebook import Document, DocumentChunk
from app.models.reading import GeneratedPassage, ReadingAnswer, ReadingSession
from app.services import llm_service
from app.services.gamification_service import award_activity


# Cache tra từ trong bộ nhớ: Ollama 7B mất vài giây/lần nên hover lại cùng từ+câu phải tức thì.
_LOOKUP_CACHE: OrderedDict[tuple[str, str], dict[str, object]] = OrderedDict()
_LOOKUP_CACHE_LIMIT = 200


_DICTIONARY_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"
_CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


async def _fetch_dictionary_candidates(term: str) -> list[dict[str, str]]:
	"""Tối đa 4 nghĩa tiếng Anh thật từ Free Dictionary; 404/lỗi mạng/timeout → [] để dùng đường lui."""
	try:
		async with httpx.AsyncClient(timeout=4.0) as client:
			response = await client.get(_DICTIONARY_URL + quote(term.strip().lower()))
		if response.status_code != 200:
			return []
		entries = response.json()
	except (httpx.HTTPError, ValueError):
		return []
	meanings = [
		meaning
		for entry in entries
		if isinstance(entry, dict)
		for meaning in entry.get("meanings", [])
	]
	picked: list[dict[str, str]] = []
	seen: set[str] = set()
	# Nghĩa đầu của mỗi loại từ trước, rồi mới tới nghĩa thứ hai — để đa dạng loại từ trước.
	for depth in (0, 1):
		for meaning in meanings:
			definitions = meaning.get("definitions", [])
			if depth >= len(definitions):
				continue
			text = definitions[depth].get("definition")
			if not text or text in seen:
				continue
			seen.add(text)
			picked.append(
				{
					"part_of_speech": meaning.get("partOfSpeech") or "",
					"definition": text,
					"example": definitions[depth].get("example") or "",
				}
			)
	return picked[:4]


_VIETNAMESE_CHARS = set("ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ")


def _is_vietnamese(text: str) -> bool:
	"""Model 7B đôi khi trả nguyên tiếng Anh cho phần nghĩa; câu tiếng Việt thật luôn có dấu/đ."""
	return any(char in _VIETNAMESE_CHARS for char in text.lower())


def _merge_translated_senses(candidates: list[dict[str, str]], raw: dict) -> list[dict[str, str]]:
	"""Ghép bản dịch/level của Ollama vào nghĩa từ điển; nghĩa hợp ngữ cảnh lên đầu, còn lại theo level."""
	# Ghép theo "index" model trả về (không theo vị trí): model 7B hay đảo thứ tự các mục.
	by_index = {
		item["index"]: item
		for item in raw.get("items", [])
		if isinstance(item.get("index"), int) and _is_vietnamese(item.get("meaning_vi", ""))
	}
	senses = []
	sense_by_index: dict[int, dict[str, str]] = {}
	for index, candidate in enumerate(candidates):
		item = by_index.get(index)
		if item is None:
			continue
		sense = {
			"part_of_speech": candidate["part_of_speech"],
			"level": item.get("level", "B1"),
			"meaning_vi": item["meaning_vi"],
			"example_en": candidate["example"],
		}
		senses.append(sense)
		sense_by_index[index] = sense
	best_sense = sense_by_index.get(raw.get("best_index"))
	rest = [sense for sense in senses if sense is not best_sense]
	rest.sort(key=lambda sense: _CEFR_ORDER.index(sense["level"]) if sense["level"] in _CEFR_ORDER else 99)
	return ([best_sense] if best_sense else []) + rest


async def lookup_term(term: str, context_sentence: str) -> dict[str, object]:
	"""Tra từ bằng Ollama (không tốn quota Gemini): nghĩa tiếng Việt chia theo sense + level CEFR."""
	key = (term.strip().lower(), context_sentence.strip().lower()[:300])
	cached = _LOOKUP_CACHE.get(key)
	if cached is not None:
		_LOOKUP_CACHE.move_to_end(key)
		return cached

	# Ưu tiên nghĩa THẬT từ từ điển rồi nhờ Ollama dịch + gán level (đáng tin hơn để model tự bịa
	# nghĩa); từ điển không có/sập thì để Ollama trả 1 nghĩa hợp ngữ cảnh.
	candidates = await _fetch_dictionary_candidates(term)
	if candidates:
		raw = await llm_service.translate_word_senses(
			term.strip(), context_sentence, [candidate["definition"] for candidate in candidates]
		)
		senses = _merge_translated_senses(candidates, raw)
	else:
		raw = await llm_service.lookup_word_vi(term.strip(), context_sentence)
		senses = [sense for sense in raw.get("senses", []) if _is_vietnamese(sense.get("meaning_vi", ""))]
	if not senses:
		# Model trả rỗng/lệch schema — báo ai_bad_output để client fallback.
		raise llm_service.AIServiceError("word_lookup_empty", "ai_bad_output")

	result = {
		"definition": senses[0]["meaning_vi"],
		"synonyms": raw.get("synonyms", [])[:5],
		"antonyms": raw.get("antonyms", [])[:5],
		"example_sentence": senses[0].get("example_en") or context_sentence,
		"ipa": raw.get("ipa") or None,
		"senses": senses[:3],
	}
	_LOOKUP_CACHE[key] = result
	if len(_LOOKUP_CACHE) > _LOOKUP_CACHE_LIMIT:
		_LOOKUP_CACHE.popitem(last=False)
	return result


async def create_classic_session(
	db: AsyncSession,
	user_id: uuid.UUID,
	document_id: uuid.UUID,
	num_questions: int,
) -> ReadingSession:
	# Chỉ tài liệu ready và thuộc user mới được dùng làm Classic Mode.
	document = await db.scalar(
		select(Document).where(
			Document.id == document_id,
			Document.user_id == user_id,
		)
	)
	if document is None:
		raise ValueError("document_not_found")
	if document.status != "ready":
		raise ValueError("document_not_ready")

	# Lấy tối đa num_questions chunk đại diện; thiếu chunk thì giảm số câu.
	result = await db.execute(
		select(DocumentChunk)
		.where(DocumentChunk.document_id == document_id)
		.order_by(DocumentChunk.chunk_index.asc())
		.limit(num_questions)
	)
	chunks = list(result.scalars().all())
	if not chunks:
		raise ValueError("document_has_no_chunks")

	session = ReadingSession(
		user_id=user_id,
		document_id=document_id,
		mode="classic",
	)
	db.add(session)
	await db.flush()

	# Đây là fallback deterministic trước khi LLM structured output được nối.
	# Đáp án đúng luôn ở index 0 nhưng không được đưa vào response public.
	for chunk in chunks:
		content = chunk.content.strip()
		question = f"Which statement is supported by the document section?"
		db.add(
			ReadingAnswer(
				reading_session_id=session.id,
				question=question,
				options=[content, "The document provides no relevant information.", "The topic is unrelated to learning.", "The section contains only a title."],
				correct_option_index=0,
				source_chunk_id=chunk.id,
			)
		)

	await db.commit()
	await db.refresh(session)
	return session


async def create_skim_scan_session(
	db: AsyncSession,
	user_id: uuid.UUID,
	level: str,
	topic: str | None,
	document_id: uuid.UUID | None,
	num_questions: int = 3,
) -> tuple[ReadingSession, GeneratedPassage]:
	"""Tạo Skim & Scan session. `document_id` set → passage là excerpt THẬT từ tài liệu
	user đã upload (không AI-sinh); `topic` set → passage do LLM sinh tự do.

	LLM ở đây theo settings.llm_provider (backend/.env: ollama, chạy local — không dùng Gemini).
	Câu hỏi trắc nghiệm luôn do LLM đó sinh (bám passage) ở cả 2 nhánh — chỉ nguồn của
	passage khác nhau, đúng yêu cầu "không chỉ AI generate mà còn dùng file user upload".
	"""
	if document_id is not None:
		document = await db.scalar(
			select(Document).where(Document.id == document_id, Document.user_id == user_id)
		)
		if document is None:
			raise ValueError("document_not_found")
		if document.status != "ready":
			raise ValueError("document_not_ready")

		chunk = await db.scalar(
			select(DocumentChunk)
			.where(DocumentChunk.document_id == document_id)
			.order_by(func.random())
			.limit(1)
		)
		if chunk is None:
			raise ValueError("document_has_no_chunks")

		passage = GeneratedPassage(
			user_id=user_id,
			source_document_id=document_id,
			level=level,
			title=document.title,
			content=chunk.content,
			word_count_label=f"{len(chunk.content.split())} words",
		)
	else:
		generated = await llm_service.generate_skim_scan_passage(topic, level)
		passage = GeneratedPassage(
			user_id=user_id,
			topic=topic,
			level=level,
			title=generated["title"],
			content=generated["content"],
			word_count_label=f"{len(generated['content'].split())} words",
			target_vocab_words=generated["target_vocab_words"],
		)

	db.add(passage)
	await db.flush()

	questions = await llm_service.generate_skim_scan_questions(passage.content, level, num_questions)

	session = ReadingSession(
		user_id=user_id,
		generated_passage_id=passage.id,
		mode="skim_scan",
	)
	db.add(session)
	await db.flush()

	for question in questions:
		db.add(
			ReadingAnswer(
				reading_session_id=session.id,
				question=question["question_text"],
				options=question["options"],
				correct_option_index=question["correct_option_index"],
			)
		)

	await db.commit()
	await db.refresh(session)
	await db.refresh(passage)
	return session, passage


async def get_owned_session(
	db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID
) -> ReadingSession:
	# Ownership filter biến session của user khác thành 404 ở router.
	session = await db.scalar(
		select(ReadingSession).where(
			ReadingSession.id == session_id,
			ReadingSession.user_id == user_id,
		)
	)
	if session is None:
		raise ValueError("session_not_found")
	return session


async def get_session_answers(
	db: AsyncSession, session_id: uuid.UUID
) -> list[ReadingAnswer]:
	# Lấy toàn bộ câu hỏi/đáp án của 1 session, dùng cả khi tạo session lẫn khi chấm điểm.
	result = await db.execute(
		select(ReadingAnswer)
		.where(ReadingAnswer.reading_session_id == session_id)
		.order_by(ReadingAnswer.created_at.asc())
	)
	return list(result.scalars().all())


async def submit_classic_session(
	db: AsyncSession,
	user_id: uuid.UUID,
	session_id: uuid.UUID,
	answers: list[tuple[uuid.UUID, int]],
	duration_seconds: int | None = None,
) -> tuple[float, list[ReadingAnswer]]:
	# Chấm điểm 1 session (dùng chung cho cả Classic Mode và Skim & Scan).
	session = await get_owned_session(db, user_id, session_id)
	reading_answers = await get_session_answers(db, session.id)

	# Submit lần hai trả đúng kết quả đã lưu, không tạo answer trùng.
	if session.completed_at is not None:
		return float(session.score or 0), reading_answers

	answer_by_id = {answer.id: answer for answer in reading_answers}
	for question_id, selected_index in answers:
		answer = answer_by_id.get(question_id)
		if answer is None:
			raise ValueError("question_not_found")
		if selected_index >= len(answer.options):
			raise ValueError("invalid_option")
		answer.selected_option_index = selected_index
		answer.is_correct = selected_index == answer.correct_option_index

	# Câu không trả lời được tính sai theo business rule Classic/Skim chung.
	correct_count = sum(answer.is_correct is True for answer in reading_answers)
	score = round(correct_count / len(reading_answers), 2) if reading_answers else 0
	session.score = score
	session.completed_at = datetime.now(timezone.utc)
	# Chỉ tới được đây ở lần chấm đầu (nộp lại đã return sớm ở trên) nên không cộng XP trùng.
	await award_activity(db, user_id, "reading_completed", score=float(score) * 100, duration_seconds=duration_seconds)
	await db.commit()
	return score, reading_answers
