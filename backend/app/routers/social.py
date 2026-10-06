from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import social_service

# Backlog 4.4 (nhật ký giọng nói) và 4.6 (bạn bè + bảng xếp hạng).
diary_router = APIRouter(prefix="/diary", tags=["voice-diary"])
friends_router = APIRouter(prefix="/friends", tags=["friends"])

_STATUS = {
	"diary_entry_not_found": 404,
	"request_not_found": 404,
	"diary_full": 409,
	"audio_too_large": 413,
}


def _raise(error: ValueError) -> None:
	raise HTTPException(_STATUS.get(str(error), 400), detail=str(error)) from error


def _entry(e) -> dict:
	return {
		"id": str(e.id),
		"created_at": e.created_at.isoformat(),
		"duration_seconds": e.duration_seconds,
		"transcript": e.transcript,
		"words_per_minute": e.words_per_minute,
	}


@diary_router.post("", status_code=status.HTTP_201_CREATED)
async def add_entry(
	audio: UploadFile = File(...),
	duration_seconds: int = Query(gt=0, le=social_service.MAX_DIARY_SECONDS),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> dict:
	try:
		return _entry(await social_service.add_diary_entry(db, current_user.id, audio, duration_seconds))
	except ValueError as error:
		_raise(error)


@diary_router.get("")
async def list_entries(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
	return [_entry(e) for e in await social_service.list_diary(db, current_user.id)]


@diary_router.get("/{entry_id}/audio")
async def entry_audio(entry_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
	try:
		entry = await social_service.get_diary_entry(db, current_user.id, entry_id)
	except ValueError as error:
		_raise(error)
	path = social_service.diary_path(entry)
	if not path.exists():
		raise HTTPException(404, detail="diary_entry_not_found")
	return FileResponse(path)


@diary_router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(entry_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Response:
	try:
		await social_service.delete_diary_entry(db, current_user.id, entry_id)
	except ValueError as error:
		_raise(error)
	return Response(status_code=204)


class FriendRequest(BaseModel):
	email: EmailStr


@friends_router.get("")
async def friends(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
	return await social_service.overview(db, current_user.id)


@friends_router.post("/requests", status_code=status.HTTP_202_ACCEPTED)
async def send_request(
	request: FriendRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
	await social_service.send_request(db, current_user, request.email)
	# Luôn trả cùng một nội dung để không lộ email nào có tài khoản.
	return {"detail": "If that account exists, a friend request was sent."}


@friends_router.post("/{friendship_id}/accept", status_code=status.HTTP_204_NO_CONTENT)
async def accept(friendship_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Response:
	try:
		await social_service.accept(db, current_user.id, friendship_id)
	except ValueError as error:
		_raise(error)
	return Response(status_code=204)


@friends_router.delete("/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(friendship_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Response:
	try:
		await social_service.remove(db, current_user.id, friendship_id)
	except ValueError as error:
		_raise(error)
	return Response(status_code=204)


@friends_router.get("/leaderboard")
async def leaderboard(
	period: str = Query(default="all", pattern="^(all|week)$"),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[dict]:
	return await social_service.leaderboard(db, current_user, period)
