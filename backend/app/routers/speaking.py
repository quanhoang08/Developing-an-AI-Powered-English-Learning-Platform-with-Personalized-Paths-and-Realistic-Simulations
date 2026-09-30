from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.speaking import ConversationTurn
from app.models.user import User
from app.schemas.speaking import (
	PhrasebookEntryResponse,
	PhrasebookSaveRequest,
	ScenarioResponse,
	SessionCreateRequest,
	SessionCreateResponse,
	SessionDetailResponse,
	SlangPhraseResponse,
	SuggestedPhrase,
	TurnResponse,
)
from app.services import speaking_service

# Router chỉ gọi speaking_service, không gọi thẳng speech_service/llm_service (mục 6 spec).
router = APIRouter(prefix="/speaking", tags=["speaking"])

_BUSINESS_ERROR_STATUS = {
	"scenario_not_found": status.HTTP_404_NOT_FOUND,
	"session_not_found": status.HTTP_404_NOT_FOUND,
	"turn_audio_not_found": status.HTTP_404_NOT_FOUND,
	"turn_not_found": status.HTTP_404_NOT_FOUND,
	"slang_phrase_not_found": status.HTTP_404_NOT_FOUND,
	"session_not_active": status.HTTP_409_CONFLICT,
	"session_expired": status.HTTP_409_CONFLICT,
	"empty_transcription": status.HTTP_422_UNPROCESSABLE_ENTITY,
	"stt_service_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
}


def _raise_business_error(error: ValueError) -> None:
	code = str(error)
	raise HTTPException(
		status_code=_BUSINESS_ERROR_STATUS.get(code, status.HTTP_400_BAD_REQUEST), detail=code
	) from error


def _turn_response(turn: ConversationTurn) -> TurnResponse:
	return TurnResponse(
		turn_id=str(turn.id),
		user_transcript=turn.user_transcript,
		response_text=turn.ai_response_text,
		# URL API tải audio (có kiểm tra quyền), không lộ đường dẫn file trên server.
		response_audio_url=f"/api/speaking/turns/{turn.id}/audio" if turn.ai_response_audio_url else None,
		pronunciation_score=float(turn.pronunciation_score)
		if turn.pronunciation_score is not None
		else None,
		pronunciation_advice=turn.pronunciation_advice,
		pronunciation_assessment_failed=bool(turn.pronunciation_assessment_failed),
		intent_score=float(turn.intent_score) if turn.intent_score is not None else None,
		politeness_score=float(turn.politeness_score) if turn.politeness_score is not None else None,
		intent_feedback=turn.intent_feedback,
		politeness_feedback=turn.politeness_feedback,
		suggested_phrases=[SuggestedPhrase(**item) for item in (turn.suggested_phrases or [])],
		stt_provider_used=turn.stt_provider_used,
	)


@router.get("/scenarios", response_model=list[ScenarioResponse])
async def list_scenarios(
	formality_level: str | None = Query(default=None),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[ScenarioResponse]:
	scenarios = await speaking_service.list_scenarios(db, formality_level)
	return [
		ScenarioResponse(
			id=str(item.id),
			title=item.title,
			description=item.description,
			difficulty_level=item.difficulty_level,
			goal=item.goal,
			formality_level=item.formality_level,
		)
		for item in scenarios
	]


@router.post(
	"/sessions", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED
)
async def create_session(
	request: SessionCreateRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> SessionCreateResponse:
	try:
		session = await speaking_service.create_session(
			db,
			current_user.id,
			UUID(request.scenario_id),
			UUID(request.persona_id) if request.persona_id else None,
		)
	except ValueError as error:
		_raise_business_error(error)
	return SessionCreateResponse(session_id=str(session.id))


@router.post(
	"/sessions/{session_id}/turns", response_model=TurnResponse, status_code=status.HTTP_201_CREATED
)
async def submit_turn(
	session_id: UUID,
	audio: UploadFile = File(...),
	provider: str | None = Query(default=None),
	duration_seconds: int | None = Query(default=None, gt=0),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> TurnResponse:
	try:
		turn = await speaking_service.submit_turn(
			db, current_user.id, session_id, audio, provider, duration_seconds
		)
	except ValueError as error:
		_raise_business_error(error)
	return _turn_response(turn)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(
	session_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> SessionDetailResponse:
	try:
		session = await speaking_service.get_owned_session(db, current_user.id, session_id)
	except ValueError as error:
		_raise_business_error(error)
	turns = await speaking_service.list_turns(db, session.id)
	return SessionDetailResponse(
		session_id=str(session.id),
		scenario_id=str(session.scenario_id) if session.scenario_id else None,
		status=session.status,
		turns=[_turn_response(turn) for turn in turns],
	)


@router.get("/turns/{turn_id}/audio")
async def get_turn_reply_audio(
	turn_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> FileResponse:
	# Audio nằm trên đĩa server, client cần đường phát có kiểm tra quyền sở hữu.
	try:
		path = await speaking_service.get_turn_reply_audio_path(db, current_user.id, turn_id)
	except ValueError as error:
		_raise_business_error(error)
	return FileResponse(path, media_type="audio/wav")


@router.get("/slang", response_model=list[SlangPhraseResponse])
async def list_slang(
	formality_level: str | None = Query(default=None),
	topic: str | None = Query(default=None),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[SlangPhraseResponse]:
	items = await speaking_service.list_slang(db, formality_level, topic)
	return [
		SlangPhraseResponse(
			id=str(item.id),
			phrase_text=item.phrase_text,
			meaning=item.meaning,
			example_sentence=item.example_sentence,
			formality_level=item.formality_level,
			topic_tags=item.topic_tags or [],
			source_reference=item.source_reference,
		)
		for item in items
	]


def _entry_response(entry, source_reference: str | None) -> PhrasebookEntryResponse:
	return PhrasebookEntryResponse(
		id=str(entry.id),
		slang_phrase_id=str(entry.slang_phrase_id) if entry.slang_phrase_id else None,
		conversation_turn_id=str(entry.conversation_turn_id) if entry.conversation_turn_id else None,
		phrase_text=entry.phrase_text,
		meaning=entry.meaning,
		example_sentence=entry.example_sentence,
		formality_level=entry.formality_level,
		source_reference=source_reference,
	)


@router.post(
	"/phrasebook", response_model=PhrasebookEntryResponse, status_code=status.HTTP_201_CREATED
)
async def save_phrase(
	request: PhrasebookSaveRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> PhrasebookEntryResponse:
	try:
		entry, library = await speaking_service.save_phrase(
			db,
			current_user.id,
			UUID(request.slang_phrase_id) if request.slang_phrase_id else None,
			UUID(request.conversation_turn_id) if request.conversation_turn_id else None,
			request.phrase_text,
			request.meaning,
			request.example_sentence,
		)
	except ValueError as error:
		_raise_business_error(error)
	return _entry_response(entry, library.source_reference if library else None)


@router.get("/phrasebook", response_model=list[PhrasebookEntryResponse])
async def list_phrasebook(
	formality_level: str | None = Query(default=None),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[PhrasebookEntryResponse]:
	rows = await speaking_service.list_phrasebook(db, current_user.id, formality_level)
	return [_entry_response(entry, source) for entry, source in rows]
