from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.listening import (
	DictationCreateRequest,
	DictationCreateResponse,
	DictationErrorItem,
	DictationSubmitRequest,
	DictationSubmitResponse,
	PodcastCreateRequest,
	PodcastListItem,
	PodcastResponse,
	TranscriptResponse,
	TranscriptWordItem,
)
from app.services import podcast_service
from app.services.listening_service import (
	create_dictation_attempt,
	get_owned_attempt,
	submit_dictation_attempt,
)
from app.services.llm_service import AIServiceError
from app.services.speech_service import SpeechServiceError


# Endpoint Listening: Podcast (mục 1), Transcript (mục 2), Dictation (mục 3).
router = APIRouter(prefix="/listening", tags=["listening"])

_AUDIO_MEDIA_TYPES = {
	".wav": "audio/wav",
	".mp3": "audio/mpeg",
	".m4a": "audio/mp4",
	".webm": "audio/webm",
	".ogg": "audio/ogg",
}

_BUSINESS_ERROR_STATUS = {
	"podcast_audio_not_found": status.HTTP_404_NOT_FOUND,
	"podcast_not_found": status.HTTP_404_NOT_FOUND,
	"document_not_found": status.HTTP_404_NOT_FOUND,
	"document_not_ready": status.HTTP_400_BAD_REQUEST,
	"dictation_attempt_not_found": status.HTTP_404_NOT_FOUND,
	"podcast_not_ready": status.HTTP_400_BAD_REQUEST,
	"podcast_has_no_transcript": status.HTTP_400_BAD_REQUEST,
	"segment_range_has_no_words": status.HTTP_400_BAD_REQUEST,
}


def _raise_business_error(error: ValueError) -> None:
	code = str(error)
	raise HTTPException(
		status_code=_BUSINESS_ERROR_STATUS.get(code, status.HTTP_400_BAD_REQUEST),
		detail=code,
	) from error


@router.post(
	"/dictation",
	response_model=DictationCreateResponse,
	status_code=status.HTTP_201_CREATED,
)
async def create_dictation(
	request: DictationCreateRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> DictationCreateResponse:
	segment_ms = (
		(request.segment_range.start_ms, request.segment_range.end_ms)
		if request.segment_range
		else None
	)
	try:
		attempt = await create_dictation_attempt(
			db, current_user.id, UUID(request.podcast_id), segment_ms
		)
	except ValueError as error:
		_raise_business_error(error)
	except SpeechServiceError as error:
		# Cắt audio thất bại (file gốc lỗi/không đọc được) — 503 giống pattern AIServiceError.
		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
		) from error

	return DictationCreateResponse(
		attempt_id=str(attempt.id), audio_url=f"/api/listening/dictation/{attempt.id}/audio"
	)


@router.post("/dictation/{attempt_id}/submit", response_model=DictationSubmitResponse)
async def submit_dictation(
	attempt_id: UUID,
	request: DictationSubmitRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> DictationSubmitResponse:
	try:
		attempt = await submit_dictation_attempt(
			db, current_user.id, attempt_id, request.transcribed_text, request.duration_seconds
		)
	except ValueError as error:
		_raise_business_error(error)

	return DictationSubmitResponse(
		score=float(attempt.accuracy_score),
		errors=[
			DictationErrorItem(type=item["type"], word=item["word"], position=item["position"])
			for item in (attempt.diff_result or [])
		],
	)


def _podcast_response(podcast) -> PodcastResponse:
	return PodcastResponse(
		id=str(podcast.id),
		status=podcast.status,
		# URL API tải audio, không lộ đường dẫn file trên server.
		audio_url=f"/api/listening/podcasts/{podcast.id}/audio" if podcast.audio_url else None,
		persona_id=str(podcast.persona_id) if podcast.persona_id else None,
		duration_seconds=podcast.duration_seconds,
	)


@router.post("/podcasts", response_model=PodcastResponse, status_code=status.HTTP_201_CREATED)
async def create_podcast(
	request: PodcastCreateRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> PodcastResponse:
	try:
		podcast = await podcast_service.create_podcast(
			db,
			current_user.id,
			UUID(request.document_id),
			UUID(request.persona_id) if request.persona_id else None,
		)
	except ValueError as error:
		_raise_business_error(error)
	except (SpeechServiceError, AIServiceError) as error:
		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
		) from error
	return _podcast_response(podcast)


@router.get("/podcasts", response_model=list[PodcastListItem])
async def list_podcasts(
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[PodcastListItem]:
	rows = await podcast_service.list_podcasts(db, current_user.id)
	return [
		PodcastListItem(
			id=str(podcast.id),
			title=title,
			status=podcast.status,
			duration_seconds=podcast.duration_seconds,
		)
		for podcast, title in rows
	]


@router.get("/podcasts/{podcast_id}/audio")
async def get_podcast_audio(
	podcast_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> FileResponse:
	try:
		path = await podcast_service.get_playable_audio_path(db, current_user.id, podcast_id)
	except ValueError as error:
		_raise_business_error(error)
	return FileResponse(path, media_type=_AUDIO_MEDIA_TYPES.get(Path(path).suffix.lower(), "audio/wav"))


@router.get("/dictation/{attempt_id}/audio")
async def get_dictation_audio(
	attempt_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> FileResponse:
	try:
		attempt = await get_owned_attempt(db, current_user.id, attempt_id)
	except ValueError as error:
		_raise_business_error(error)
	if not attempt.audio_segment_path or not Path(attempt.audio_segment_path).exists():
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dictation_audio_not_found")
	return FileResponse(attempt.audio_segment_path, media_type="audio/wav")


@router.get("/podcasts/{podcast_id}", response_model=PodcastResponse)
async def get_podcast(
	podcast_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> PodcastResponse:
	try:
		podcast = await podcast_service.get_owned_podcast(db, current_user.id, podcast_id)
	except ValueError as error:
		_raise_business_error(error)
	return _podcast_response(podcast)


@router.get("/podcasts/{podcast_id}/transcript", response_model=TranscriptResponse)
async def get_podcast_transcript(
	podcast_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> TranscriptResponse:
	try:
		words = await podcast_service.get_transcript(db, current_user.id, podcast_id)
	except ValueError as error:
		_raise_business_error(error)
	return TranscriptResponse(
		segments=[
			TranscriptWordItem(text=w.word_text, start_ms=w.start_time_ms, end_ms=w.end_time_ms)
			for w in words
		]
	)
