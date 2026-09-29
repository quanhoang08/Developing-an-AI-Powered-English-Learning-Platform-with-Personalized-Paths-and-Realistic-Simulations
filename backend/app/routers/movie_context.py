from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.movie_context import MovieContextMatchItem, MovieContextSearchResponse, SubtitleCue
from app.services import movie_context_service
from app.services.speech_service import SpeechServiceError


# Movie Delivery Context (api-spec.md mục 8): video có phụ đề khớp trước, không có thì TTS fallback.
router = APIRouter(prefix="/movie-context", tags=["movie-context"])

_BASE = "/api/movie-context/matches"


def _not_found(error: ValueError) -> HTTPException:
	return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


def _item(view: dict) -> MovieContextMatchItem:
	match_id = str(view["match_id"])
	is_video = view["source_type"] == "real_video"
	return MovieContextMatchItem(
		**{**view, "match_id": match_id},
		audio_url=None if is_video else f"{_BASE}/{match_id}/audio",
		video_url=f"{_BASE}/{match_id}/video" if is_video else None,
	)


@router.get("/search", response_model=MovieContextSearchResponse)
async def search_phrase(
	phrase: str = Query(min_length=1, max_length=255),
	persona_id: UUID | None = Query(default=None),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> MovieContextSearchResponse:
	phrase = phrase.strip()
	if not phrase:
		raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="phrase_required")
	try:
		views = await movie_context_service.search(db, current_user.id, phrase, persona_id)
	except SpeechServiceError as error:
		raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
	# AIServiceError do handler toàn cục trong main.py xử lý.
	return MovieContextSearchResponse(matches=[_item(view) for view in views])


@router.post("/matches/{match_id}/save", status_code=status.HTTP_204_NO_CONTENT)
async def save_match(
	match_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> Response:
	try:
		await movie_context_service.save_match(db, current_user.id, match_id)
	except ValueError as error:
		raise _not_found(error) from error
	return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/matches/{match_id}/audio")
async def get_match_audio(
	match_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> FileResponse:
	# Audio nằm trên đĩa server -> cần đường phát có kiểm tra quyền sở hữu (giống speaking turns).
	try:
		path = await movie_context_service.get_match_audio_path(db, current_user.id, match_id)
	except ValueError as error:
		raise _not_found(error) from error
	return FileResponse(path, media_type="audio/wav")


@router.get("/matches/{match_id}/subtitles", response_model=list[SubtitleCue])
async def get_match_subtitles(
	match_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[SubtitleCue]:
	try:
		lines = await movie_context_service.get_match_subtitles(db, current_user.id, match_id)
	except ValueError as error:
		raise _not_found(error) from error
	return [SubtitleCue(**line) for line in lines]


@router.get("/matches/{match_id}/video")
async def get_match_video(
	match_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> FileResponse:
	try:
		path = await movie_context_service.get_match_video_path(db, current_user.id, match_id)
	except ValueError as error:
		raise _not_found(error) from error
	return FileResponse(path, media_type="video/mp4")
