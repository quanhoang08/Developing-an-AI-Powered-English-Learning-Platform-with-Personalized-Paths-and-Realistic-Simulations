from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import pronunciation_service, speech_service

# Backlog 4.1-4.5: phát âm theo lỗi người Việt, cặp âm, shadowing, nói thầm.
router = APIRouter(prefix="/pronunciation", tags=["pronunciation"])

_STATUS = {
	"sentence_not_found": 404,
	"prompt_not_found": 404,
	"pronunciation_service_unavailable": 503,
	"answer_too_short": 422,
	"answer_off_topic": 422,
}


def _raise(error: ValueError) -> None:
	raise HTTPException(_STATUS.get(str(error), 400), detail=str(error)) from error


class PairAnswer(BaseModel):
	id: str = Field(pattern=r"^\d+-[01]$")
	choice: str = Field(min_length=1, max_length=30)


class PairsCheckRequest(BaseModel):
	answers: list[PairAnswer] = Field(min_length=1, max_length=18)


class SilentRequest(BaseModel):
	prompt_id: int
	text: str = Field(min_length=1, max_length=1000)


@router.get("/sentences")
async def sentences(current_user: User = Depends(get_current_user)) -> list[dict]:
	return pronunciation_service.sentence_list()


@router.get("/sentences/{sentence_id}/audio")
async def sentence_audio(sentence_id: str, current_user: User = Depends(get_current_user)) -> Response:
	# Âm mẫu Azure TTS để shadowing và so sóng âm; trình duyệt tải kèm token nên là endpoint có xác thực.
	try:
		return Response(pronunciation_service.sentence_audio(sentence_id), media_type="audio/wav")
	except ValueError as error:
		_raise(error)
	except speech_service.SpeechServiceError as error:
		raise HTTPException(503, detail="pronunciation_service_unavailable") from error


@router.post("/sentences/{sentence_id}/assess")
async def assess(
	sentence_id: str,
	audio: UploadFile = File(...),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> dict:
	try:
		return await pronunciation_service.assess(db, current_user.id, sentence_id, audio)
	except ValueError as error:
		_raise(error)


@router.get("/pairs/quiz")
async def pairs_quiz(count: int = Query(8, ge=1, le=18), current_user: User = Depends(get_current_user)) -> list[dict]:
	return pronunciation_service.pairs_quiz(count)


@router.post("/pairs/check")
async def pairs_check(request: PairsCheckRequest, current_user: User = Depends(get_current_user)) -> dict:
	try:
		return pronunciation_service.pairs_check([a.model_dump() for a in request.answers])
	except ValueError as error:
		_raise(error)


@router.get("/silent/prompt")
async def silent_prompt(current_user: User = Depends(get_current_user)) -> dict:
	return pronunciation_service.silent_prompt()


@router.post("/silent")
async def silent(
	request: SilentRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
	try:
		return await pronunciation_service.silent_answer(db, current_user.id, request.prompt_id, request.text)
	except ValueError as error:
		_raise(error)
