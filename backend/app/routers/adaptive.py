from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.adaptive import (
	HabitsResponse,
	QuizAttemptRequest,
	QuizAttemptResponse,
	QuizGenerateRequest,
	QuizResponse,
	ReviewQueueItem,
	UserErrorResponse,
)
from app.services import adaptive_service


router = APIRouter(prefix="/adaptive", tags=["adaptive"])

# Mã lỗi nghiệp vụ từ service -> HTTP status; lỗi lạ được ném lại thay vì nuốt thành 400.
_ERROR_STATUS = {
	"invalid_error_type": status.HTTP_422_UNPROCESSABLE_ENTITY,
	"no_errors_to_practice": status.HTTP_409_CONFLICT,
	"quiz_not_found": status.HTTP_404_NOT_FOUND,
	"answer_count_mismatch": status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def _http_error(error: ValueError) -> HTTPException:
	code = str(error)
	if code not in _ERROR_STATUS:
		raise error
	return HTTPException(status_code=_ERROR_STATUS[code], detail=code)


@router.get("/errors", response_model=list[UserErrorResponse])
async def list_errors(
	error_type: str | None = None,
	limit: int = Query(default=20, ge=1, le=100),
	offset: int = Query(default=0, ge=0),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[dict]:
	return await adaptive_service.list_errors(db, current_user.id, error_type, limit, offset)


@router.get("/review-queue", response_model=list[ReviewQueueItem])
async def get_review_queue(
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[dict]:
	return await adaptive_service.get_review_queue(db, current_user.id)


@router.post("/quizzes/generate", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
async def generate_quiz(
	payload: QuizGenerateRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> QuizResponse:
	try:
		quiz = await adaptive_service.generate_quiz(
			db, current_user.id, payload.focus_error_types, payload.num_questions
		)
	except ValueError as error:
		raise _http_error(error) from error
	return QuizResponse(quiz_id=quiz.id, questions=adaptive_service.public_questions(quiz.questions))


@router.post("/quizzes/{quiz_id}/attempts", response_model=QuizAttemptResponse)
async def submit_quiz_attempt(
	quiz_id: UUID,
	payload: QuizAttemptRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> dict:
	try:
		return await adaptive_service.submit_quiz_attempt(db, current_user.id, quiz_id, payload.answers)
	except ValueError as error:
		raise _http_error(error) from error


@router.get("/habits", response_model=HabitsResponse)
async def get_habits(
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> dict:
	return await adaptive_service.get_habits(db, current_user.id)
