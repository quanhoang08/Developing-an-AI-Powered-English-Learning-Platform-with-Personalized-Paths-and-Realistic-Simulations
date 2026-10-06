from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.grammar import (
	GrammarAttemptItem,
	GrammarDaily,
	GrammarQuestion,
	GrammarSubmitRequest,
	GrammarSubmitResponse,
)
from app.services import grammar_service


# Backlog 3.8/3.9: ngân hàng ngữ pháp cố định, đề lấy ngẫu nhiên, chấm ở server, lưu lịch sử từng lượt.
router = APIRouter(prefix="/grammar", tags=["grammar"])


@router.get("/quiz", response_model=list[GrammarQuestion])
async def grammar_quiz(
	topic: Literal["tenses", "articles", "prepositions", "agreement", "word_form", "error_correction"] | None = None,
	count: int = Query(12, ge=1, le=36),
	current_user: User = Depends(get_current_user),
) -> list[dict]:
	return grammar_service.make_quiz(topic, count)


@router.get("/daily", response_model=GrammarDaily)
async def grammar_daily(
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> dict:
	return await grammar_service.daily_lesson(db, current_user.id)


@router.get("/attempts", response_model=list[GrammarAttemptItem])
async def grammar_attempts(
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
):
	return await grammar_service.history(db, current_user.id)


@router.post("/submit", response_model=GrammarSubmitResponse)
async def grammar_submit(
	request: GrammarSubmitRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> dict:
	try:
		return await grammar_service.grade_quiz(
			db, current_user.id, [a.model_dump() for a in request.answers], request.topic
		)
	except ValueError as error:
		raise HTTPException(status_code=422, detail=str(error)) from error
