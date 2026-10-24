from fastapi import APIRouter, Depends, HTTPException, WebSocket
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import games_service, speed_quiz_service


router = APIRouter(prefix="/games", tags=["games"])


class WordleGuess(BaseModel):
	guess: str = Field(min_length=1, max_length=20)
	attempt: int = Field(ge=1, le=games_service.WORDLE_MAX_GUESSES)


class MemoryMatchResult(BaseModel):
	pairs: int = Field(ge=1, le=20)
	moves: int = Field(ge=1, le=400)


@router.get("/wordle")
async def wordle_status(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
	return await games_service.wordle_status(db, current_user.id)


@router.post("/wordle/guess")
async def wordle_guess(
	request: WordleGuess, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
	try:
		return await games_service.wordle_guess(db, current_user.id, request.guess, request.attempt)
	except ValueError as error:
		raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/memory-match/complete")
async def memory_match_complete(
	request: MemoryMatchResult, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
	try:
		return await games_service.memory_match_complete(db, current_user.id, request.pairs, request.moves)
	except ValueError as error:
		raise HTTPException(status_code=422, detail=str(error)) from error


class ScoreResult(BaseModel):
	score: int = Field(ge=0, le=100000)


class ChainTurn(BaseModel):
	chain: list[str] = Field(default_factory=list, max_length=40)
	word: str = Field(min_length=1, max_length=20)


class DetectiveCheck(BaseModel):
	passage_id: int
	picks: list[int] = Field(max_length=50)


@router.post("/{game}/complete")
async def score_game_complete(
	game: str, request: ScoreResult, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
	try:
		return await games_service.score_game_complete(db, current_user.id, game, request.score)
	except LookupError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
	except ValueError as error:
		raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/word-chain/turn")
async def word_chain_turn(request: ChainTurn, current_user: User = Depends(get_current_user)) -> dict:
	try:
		return games_service.word_chain_turn([w.lower() for w in request.chain], request.word)
	except ValueError as error:
		raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/grammar-detective")
async def grammar_detective(exclude: int | None = None, current_user: User = Depends(get_current_user)) -> dict:
	return games_service.detective_new(exclude)


@router.post("/grammar-detective/check")
async def grammar_detective_check(
	request: DetectiveCheck, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
	try:
		return await games_service.detective_check(db, current_user.id, request.passage_id, request.picks)
	except LookupError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/quests")
async def list_quests(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
	return await games_service.list_quests(db, current_user.id)


@router.post("/quests/{quest_id}/claim")
async def claim_quest(
	quest_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
	try:
		return {"xp_awarded": await games_service.claim_quest(db, current_user.id, quest_id)}
	except LookupError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
	except ValueError as error:
		raise HTTPException(status_code=409, detail=str(error)) from error


@router.websocket("/speed-quiz/ws")
async def speed_quiz_ws(websocket: WebSocket, token: str = "") -> None:
	# Token trên query vì WebSocket của trình duyệt không gửi được header Authorization.
	await speed_quiz_service.handle(websocket, token)
