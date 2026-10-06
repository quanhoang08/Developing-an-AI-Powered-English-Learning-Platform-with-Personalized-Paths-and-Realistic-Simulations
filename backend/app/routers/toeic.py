from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.toeic import (
	ToeicPracticeRequest,
	ToeicPracticeResponse,
	ToeicQuestion,
	ToeicResult,
	ToeicSubmitRequest,
	ToeicSubmitResponse,
	ToeicSummary,
)
from app.services import toeic_service
from app.services.vi_contrast import CONTRAST


# Luyện TOEIC-style: đề gốc do AI sinh (không phải đề ETS), chấm ở server.
router = APIRouter(prefix="/toeic", tags=["toeic"])


@router.post("/practice", response_model=ToeicPracticeResponse)
async def start_practice(
	request: ToeicPracticeRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> ToeicPracticeResponse:
	return _practice_response(await toeic_service.create_practice(db, current_user.id, request.part, request.count))


def _practice_response(attempt) -> ToeicPracticeResponse:
	return ToeicPracticeResponse(
		attempt_id=str(attempt.id),
		part=attempt.part,
		time_limit_seconds=toeic_service.time_limit(attempt),
		questions=[
			ToeicQuestion(**{k: q[k] for k in ("prompt", "passage", "options")}, image=q.get("image"), credit=q.get("credit"), part=q.get("part"), group=q.get("group"))
			for q in attempt.questions
		],
	)


@router.post("/mock", response_model=ToeicPracticeResponse)
async def start_mock(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> ToeicPracticeResponse:
	"""Đề thi thử Part 1-7 ghép từ ngân hàng đã kiểm chứng; ngân hàng quá ít thì 409."""
	try:
		return _practice_response(await toeic_service.create_mock(db, current_user.id))
	except ValueError as error:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/part1/images/{name}")
async def part1_image(name: str, current_user: User = Depends(get_current_user)) -> FileResponse:
	path = toeic_service.part1_image_path(name)  # chỉ ảnh trong danh sách khai báo
	if path is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image_not_found")
	return FileResponse(path, media_type="image/jpeg")


@router.post("/{attempt_id}/submit", response_model=ToeicSubmitResponse)
async def submit_practice(
	attempt_id: UUID,
	request: ToeicSubmitRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> ToeicSubmitResponse:
	try:
		attempt = await toeic_service.submit(db, current_user.id, attempt_id, request.picks, request.duration_seconds)
	except ValueError as error:
		code = str(error)
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND if code == "attempt_not_found" else status.HTTP_422_UNPROCESSABLE_ENTITY,
			detail=code,
		) from error
	results = [
		ToeicResult(
			chosen=pick,
			correct_index=q["correct_index"],
			is_correct=pick == q["correct_index"],
			explanation_vi=q["explanation_vi"],
			contrast_vi=None if pick == q["correct_index"] else CONTRAST[f"toeic_part{q.get('part', attempt.part)}"],
		)
		for q, pick in zip(attempt.questions, attempt.picks)
	]
	response = ToeicSubmitResponse(
		score=float(attempt.score), correct_count=attempt.correct_count, total=len(results), results=results
	)
	if attempt.part == 0:
		stats = toeic_service.part_breakdown(attempt)
		response.by_part = [{"part": p, "correct": c, "total": t} for p, (c, t) in stats.items()]
		response.estimate = toeic_service.estimate(stats)
	return response


@router.get("/summary", response_model=ToeicSummary)
async def toeic_summary(
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> dict:
	return await toeic_service.summary(db, current_user.id)
