from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.errors import ai_http_error
from app.database import get_db
from app.models.user import User
from app.schemas.reading import (
	ClassicSessionCreate,
	ClassicSessionResponse,
	GuessContextCreate,
	GuessContextResponse,
	GuessContextSubmit,
	GuessContextSubmitResponse,
	LookupRequest,
	LookupResponse,
	ReadingQuestion,
	ReadingResult,
	ReadingSubmitRequest,
	ReadingSubmitResponse,
	SkimScanSessionCreate,
	SkimScanSessionResponse,
	StoryCreate,
	StoryResponse,
)
from app.schemas.rearrange import RearrangeBlock, RearrangeResponse, RearrangeSubmit, RearrangeSubmitResponse
from app.services import rearrange_service
from app.services.llm_service import AIServiceError
from app.services.reading_service import (
	create_classic_session,
	create_skim_scan_session,
	get_session_answers,
	lookup_term,
	submit_classic_session,
)
from app.services.vocab_practice_service import (
	create_guess_attempt,
	create_story,
	submit_guess_attempt,
)


# Endpoint Reading: tra từ, Classic Mode, Skim & Scan, và submit chấm điểm dùng chung.
router = APIRouter(prefix="/reading", tags=["reading"])
# Custom Story nằm ở /api/stories theo api-spec.md mục 3 (không nằm dưới /reading).
stories_router = APIRouter(prefix="/stories", tags=["reading"])


@router.post("/lookup", response_model=LookupResponse)
async def lookup(
	request: LookupRequest,
	_current_user: User = Depends(get_current_user),
) -> LookupResponse:
	# Auth bắt buộc theo API spec; nghĩa do Ollama sinh, lỗi AI → 503 để client fallback từ điển.
	try:
		return LookupResponse(**await lookup_term(request.term, request.context_sentence))
	except ValueError as error:
		raise HTTPException(status_code=503, detail=str(error)) from error


@router.post(
	"/classic/sessions",
	response_model=ClassicSessionResponse,
	status_code=status.HTTP_201_CREATED,
)
async def create_classic_reading_session(
	request: ClassicSessionCreate,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> ClassicSessionResponse:
	# Tạo câu hỏi đầy đủ trong DB nhưng chỉ trả fields public, không lộ đáp án.
	try:
		session = await create_classic_session(
			db, current_user.id, UUID(request.document_id), request.num_questions
		)
	except ValueError as error:
		code = str(error)
		status_code = 404 if code == "document_not_found" else 400
		raise HTTPException(status_code=status_code, detail=code) from error

	answers = await get_session_answers(db, session.id)
	return ClassicSessionResponse(
		session_id=str(session.id),
		questions=[
			ReadingQuestion(
				id=str(answer.id),
				question_text=answer.question,
				options=answer.options,
			)
			for answer in answers
		],
	)


@router.post(
	"/skim-scan/sessions",
	response_model=SkimScanSessionResponse,
	status_code=status.HTTP_201_CREATED,
)
async def create_skim_scan_reading_session(
	request: SkimScanSessionCreate,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> SkimScanSessionResponse:
	# document_id → passage thật trích từ tài liệu user; topic → LLM (settings.llm_provider = ollama) tự sinh đoạn văn mới.
	try:
		session, passage = await create_skim_scan_session(
			db,
			current_user.id,
			request.level,
			request.topic,
			UUID(request.document_id) if request.document_id else None,
		)
	except ValueError as error:
		code = str(error)
		if code in {"document_not_found", "document_has_no_chunks"}:
			status_code = 404
		else:
			status_code = 400
		raise HTTPException(status_code=status_code, detail=code) from error

	answers = await get_session_answers(db, session.id)
	return SkimScanSessionResponse(
		session_id=str(session.id),
		passage_id=str(passage.id),
		title=passage.title,
		content=passage.content,
		source_document_id=str(passage.source_document_id) if passage.source_document_id else None,
		questions=[
			ReadingQuestion(id=str(answer.id), question_text=answer.question, options=answer.options)
			for answer in answers
		],
		time_limit_seconds=request.time_limit_seconds,
	)


@router.post("/sessions/{session_id}/submit", response_model=ReadingSubmitResponse)
async def submit_reading_session(
	session_id: UUID,
	request: ReadingSubmitRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> ReadingSubmitResponse:
	# Service kiểm tra ownership, option index và submit idempotency.
	try:
		score, answers = await submit_classic_session(
			db,
			current_user.id,
			session_id,
			[(UUID(answer.question_id), answer.selected_option_index) for answer in request.answers],
			request.duration_seconds,
		)
	except ValueError as error:
		code = str(error)
		status_code = 404 if code in {"session_not_found", "question_not_found"} else 400
		raise HTTPException(status_code=status_code, detail=code) from error

	return ReadingSubmitResponse(
		score=score,
		results=[
			ReadingResult(
				question_id=str(answer.id),
				correct_option_index=answer.correct_option_index,
				source_chunk_id=str(answer.source_chunk_id) if answer.source_chunk_id else None,
			)
			for answer in answers
		],
	)


@router.post(
	"/guess-context", response_model=GuessContextResponse, status_code=status.HTTP_201_CREATED
)
async def create_guess_context(
	request: GuessContextCreate,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> GuessContextResponse:
	# Không trả correct_option_index; đáp án chỉ lộ ở bước submit.
	try:
		attempt = await create_guess_attempt(
			db,
			current_user.id,
			UUID(request.vocab_item_id) if request.vocab_item_id else None,
			request.term,
		)
	except ValueError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
	except AIServiceError as error:
		raise ai_http_error(error) from error
	return GuessContextResponse(
		attempt_id=str(attempt.id),
		challenge_sentence=attempt.challenge_sentence,
		options=attempt.options,
	)


@router.post("/guess-context/{attempt_id}/submit", response_model=GuessContextSubmitResponse)
async def submit_guess_context(
	attempt_id: UUID,
	request: GuessContextSubmit,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> GuessContextSubmitResponse:
	try:
		attempt = await submit_guess_attempt(
			db, current_user.id, attempt_id, request.selected_option_index
		)
	except ValueError as error:
		code = str(error)
		raise HTTPException(status_code=404 if code == "attempt_not_found" else 400, detail=code) from error
	return GuessContextSubmitResponse(
		correct=attempt.is_correct, correct_option_index=attempt.correct_option_index
	)


@stories_router.post("", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_story(
	request: StoryCreate,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> StoryResponse:
	try:
		story, missing_terms = await create_story(
			db,
			current_user.id,
			[UUID(item_id) for item_id in request.vocab_item_ids],
			request.theme,
			request.length,
		)
	except ValueError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
	except AIServiceError as error:
		raise ai_http_error(error) from error
	return StoryResponse(id=str(story.id), content=story.generated_text, missing_terms=missing_terms)


@router.post(
	"/rearrange", response_model=RearrangeResponse, status_code=status.HTTP_201_CREATED
)
async def create_reading_rearrange(
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> RearrangeResponse:
	# Không cần input: nguồn nội dung do service chọn (lỗi cũ → bài đã đọc → AI sinh).
	try:
		attempt, blocks = await rearrange_service.create_attempt(db, current_user, rearrange_service.READING)
	except AIServiceError as error:
		raise ai_http_error(error) from error
	return RearrangeResponse(attempt_id=str(attempt.id), blocks=[RearrangeBlock(**block) for block in blocks])


@router.post("/rearrange/{attempt_id}/submit", response_model=RearrangeSubmitResponse)
async def submit_reading_rearrange(
	attempt_id: UUID,
	request: RearrangeSubmit,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> RearrangeSubmitResponse:
	try:
		result = await rearrange_service.submit_attempt(
			db, current_user.id, attempt_id, request.block_order, rearrange_service.READING
		)
	except ValueError as error:
		code = str(error)
		raise HTTPException(status_code=404 if code == "attempt_not_found" else 400, detail=code) from error
	return RearrangeSubmitResponse(**result._asdict())
