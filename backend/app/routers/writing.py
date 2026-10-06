from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.errors import ai_http_error
from app.database import get_db
from app.models.user import User
from app.models.writing import WritingSubmission
from app.schemas.writing import (
	ParaphraseAttempt,
	ParaphraseCheckResponse,
	ParaphraseItem,
	GrammarCheckRequest,
	GrammarCheckResponse,
	GrammarInsight,
	InsightResponse,
	PromptSuggestRequest,
	PromptSuggestResponse,
	RephraseCreate,
	RephraseResponse,
	RephraseSuggestion,
	RubricScores,
	StructureReport,
	SubmissionCreate,
	SubmissionResponse,
	SubmitEssayRequest,
	SubmitEssayResponse,
	WritingSubmissionDetail,
)
from app.schemas.rearrange import RearrangeBlock, RearrangeResponse, RearrangeSubmit, RearrangeSubmitResponse
from app.services import paraphrase_service, rearrange_service
from app.services.llm_service import AIServiceError
from app.utils.text_metrics import sentence_structures
from app.services.writing_service import (
	check_grammar,
	create_submission,
	get_owned_submission,
	list_insights,
	rephrase,
	submit_essay,
	suggest_prompt,
)


# Endpoint Writing: tạo đề (3 nguồn), xem chi tiết, và nộp bài + chấm điểm qua Gemini.
router = APIRouter(prefix="/writing", tags=["writing"])

_BUSINESS_ERROR_STATUS = {
	"document_not_found": status.HTTP_404_NOT_FOUND,
	"submission_not_found": status.HTTP_404_NOT_FOUND,
	"document_not_ready": status.HTTP_400_BAD_REQUEST,
	"document_has_no_chunks": status.HTTP_400_BAD_REQUEST,
	"submission_too_short": status.HTTP_400_BAD_REQUEST,
	"no_text_to_check": status.HTTP_400_BAD_REQUEST,
	"submission_not_submitted_yet": status.HTTP_400_BAD_REQUEST,
}


def _raise_business_error(error: ValueError) -> None:
	# Map mã lỗi service (ValueError) sang HTTPException đúng status code, dùng chung 3 endpoint.
	code = str(error)
	raise HTTPException(
		status_code=_BUSINESS_ERROR_STATUS.get(code, status.HTTP_400_BAD_REQUEST),
		detail=code,
	) from error


def _rubric_response(rubric_scores: dict | None) -> RubricScores | None:
	# rubric_scores là JSONB có thể None (document_summary) — bọc thành schema khi có giá trị.
	return RubricScores(**rubric_scores) if rubric_scores else None


@router.post(
	"/submissions",
	response_model=SubmissionResponse,
	status_code=status.HTTP_201_CREATED,
)
async def create_writing_submission(
	request: SubmissionCreate,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> SubmissionResponse:
	# document_id/prompt_text đã được Pydantic ràng buộc đúng theo source_type ở schema.
	try:
		submission = await create_submission(
			db,
			current_user.id,
			request.source_type,
			UUID(request.document_id) if request.document_id else None,
			request.prompt_text,
			request.certificate_style,
		)
	except ValueError as error:
		_raise_business_error(error)
	return SubmissionResponse(
		submission_id=str(submission.id),
		source_type=submission.source_type,
		prompt_text=submission.prompt_text,
	)


@router.get("/submissions/{submission_id}", response_model=WritingSubmissionDetail)
async def get_writing_submission(
	submission_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> WritingSubmissionDetail:
	# Xem lại 1 submission đã tạo (kể cả trước khi nộp bài — submitted_text lúc đó rỗng).
	try:
		submission: WritingSubmission = await get_owned_submission(db, current_user.id, submission_id)
	except ValueError as error:
		_raise_business_error(error)
	return WritingSubmissionDetail(
		id=str(submission.id),
		source_type=submission.source_type,
		prompt_text=submission.prompt_text,
		document_id=str(submission.document_id) if submission.document_id else None,
		certificate_style=submission.certificate_style,
		submitted_text=submission.submitted_text,
		overall_score=float(submission.overall_score) if submission.overall_score is not None else None,
		cefr_level=submission.cefr_level,
		ielts_band=submission.ielts_band,
		rubric_scores=_rubric_response(submission.rubric_scores),
		created_at=submission.created_at,
		completed_at=submission.completed_at,
	)


@router.get("/submissions/{submission_id}/structures", response_model=StructureReport)
async def get_submission_structures(
	submission_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> StructureReport:
	try:
		submission = await get_owned_submission(db, current_user.id, submission_id)
	except ValueError as error:
		_raise_business_error(error)
	if not submission.submitted_text.strip():
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="submission_not_submitted_yet")
	return StructureReport(**sentence_structures(submission.submitted_text))


@router.post("/submissions/{submission_id}/submit", response_model=SubmitEssayResponse)
async def submit_writing_submission(
	submission_id: UUID,
	request: SubmitEssayRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> SubmitEssayResponse:
	# Service gọi Gemini thật (coverage hoặc rubric 4 tiêu chí tùy source_type) rồi lưu DB.
	try:
		submission = await submit_essay(
			db, current_user.id, submission_id, request.submitted_text, request.duration_seconds
		)
	except ValueError as error:
		_raise_business_error(error)

	insights = await list_insights(db, submission.id)
	return SubmitEssayResponse(
		score=float(submission.overall_score),
		cefr_level=submission.cefr_level,
		ielts_band=submission.ielts_band,
		source_type=submission.source_type,
		rubric_scores=_rubric_response(submission.rubric_scores),
		insights=[
			InsightResponse(
				insight_type=insight.insight_type,
				title=insight.title,
				description=insight.description,
				original_text=insight.original_text,
				suggested_text=insight.suggested_text,
			)
			for insight in insights
		],
	)


@router.post("/prompts/suggest", response_model=PromptSuggestResponse)
async def suggest_writing_prompt(
	request: PromptSuggestRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> PromptSuggestResponse:
	# Bước chọn đề trước khi POST /submissions — free_topic+certificate_style trả nhiều lựa
	# chọn, chưa tạo submission nào (client gọi lại /submissions sau khi người học chọn 1).
	level = request.level or current_user.target_level or "b1"
	try:
		result = await suggest_prompt(
			db,
			current_user.id,
			request.source_type,
			UUID(request.document_id) if request.document_id else None,
			request.topic,
			request.certificate_style,
			level,
		)
	except ValueError as error:
		_raise_business_error(error)
	return PromptSuggestResponse(**result)


@router.post("/grammar-check", response_model=GrammarCheckResponse)
async def grammar_check(
	request: GrammarCheckRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> GrammarCheckResponse:
	# submission_id → chấm + lưu writing_insights; raw_text → preview, không lưu gì.
	try:
		errors = await check_grammar(
			db,
			current_user.id,
			UUID(request.submission_id) if request.submission_id else None,
			request.raw_text,
		)
	except ValueError as error:
		_raise_business_error(error)
	return GrammarCheckResponse(
		insights=[
			GrammarInsight(
				offset_start=error["offset_start"],
				offset_end=error["offset_end"],
				original_text=error["original_text"],
				suggested_text=error["suggested_text"],
				explanation=error["explanation"],
			)
			for error in errors
		]
	)


@router.post("/rephrase", response_model=RephraseResponse)
async def rephrase_writing_sentence(
	request: RephraseCreate,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> RephraseResponse:
	# sentence_text rỗng → model tự chọn câu yếu nhất trong bài đã nộp.
	try:
		original_sentence, rows = await rephrase(
			db, current_user.id, UUID(request.submission_id), request.sentence_text
		)
	except ValueError as error:
		_raise_business_error(error)
	return RephraseResponse(
		original_sentence=original_sentence,
		suggested_sentences=[
			RephraseSuggestion(text=row.rephrased_text, explanation=row.explanation or "")
			for row in rows
		],
	)


@router.post(
	"/rearrange", response_model=RearrangeResponse, status_code=status.HTTP_201_CREATED
)
async def create_writing_rearrange(
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> RearrangeResponse:
	# Không cần input: nguồn là lỗi ngữ pháp cũ của user, không có thì AI tự viết câu.
	try:
		attempt, blocks = await rearrange_service.create_attempt(db, current_user, rearrange_service.WRITING)
	except AIServiceError as error:
		raise ai_http_error(error) from error
	return RearrangeResponse(
		attempt_id=str(attempt.id),
		blocks=[RearrangeBlock(**block) for block in blocks],
		is_open_form=attempt.is_open_form,
	)


@router.post("/rearrange/{attempt_id}/submit", response_model=RearrangeSubmitResponse)
async def submit_writing_rearrange(
	attempt_id: UUID,
	request: RearrangeSubmit,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> RearrangeSubmitResponse:
	try:
		result = await rearrange_service.submit_attempt(
			db, current_user.id, attempt_id, request.block_order, rearrange_service.WRITING
		)
	except ValueError as error:
		code = str(error)
		raise HTTPException(status_code=404 if code == "attempt_not_found" else 400, detail=code) from error
	return RearrangeSubmitResponse(**result._asdict())


@router.get("/paraphrase-bank", response_model=list[ParaphraseItem])
async def paraphrase_bank(technique: str | None = None, current_user: User = Depends(get_current_user)) -> list[dict]:
	try:
		return paraphrase_service.list_bank(technique)
	except ValueError as error:
		raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/paraphrase-bank/{bank_id}/check", response_model=ParaphraseCheckResponse)
async def paraphrase_check(
	bank_id: int, request: ParaphraseAttempt, current_user: User = Depends(get_current_user)
) -> dict:
	try:
		return paraphrase_service.check_attempt(bank_id, request.text)
	except ValueError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
