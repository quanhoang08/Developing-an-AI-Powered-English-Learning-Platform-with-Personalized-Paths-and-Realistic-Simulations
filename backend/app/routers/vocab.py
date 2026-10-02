from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.vocab import VocabItem
from app.schemas.vocab import (
	VocabCreate,
	VocabResponse,
	VocabReviewRequest,
	VocabReviewResponse,
	VocabSentenceRequest,
	VocabSentenceResponse,
	WordFamilyResponse,
)
from app.services.vocab_service import (
	check_vocab_sentence,
	create_vocab_item,
	get_word_family,
	import_from_errors,
	list_due_vocab,
	review_vocab,
)


router = APIRouter(prefix="/vocab", tags=["vocabulary"])


def vocab_response(item: VocabItem) -> VocabResponse:
	# Chuyển ORM object thành response DTO, không trả dữ liệu nội bộ ngoài contract.
	return VocabResponse(
		id=item.id,
		term=item.term,
		definition=item.definition,
		document_id=item.document_id,
		source_url=item.source_url,
		ipa=item.ipa,
		part_of_speech=item.part_of_speech,
		example_sentence=item.example_sentence,
		synonyms=item.synonyms,
		antonyms=item.antonyms,
		created_at=item.created_at,
	)


@router.post("", response_model=VocabResponse, status_code=status.HTTP_201_CREATED)
async def create_vocab(
	request: VocabCreate,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> VocabResponse:
	# Schema đã kiểm tra đúng một nguồn; service kiểm tra ownership document.
	try:
		item = await create_vocab_item(
			db,
			current_user.id,
			request.term,
			request.definition,
			request.document_id,
			request.source_url,
			request.ipa,
			request.part_of_speech,
			request.example_sentence,
			request.synonyms,
			request.antonyms,
		)
	except ValueError as error:
		code = str(error)
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT if code == "vocab_duplicate" else status.HTTP_404_NOT_FOUND,
			detail=code,
		) from error
	return vocab_response(item)


@router.post("/from-errors", response_model=list[VocabResponse])
async def vocab_from_errors(
	limit: int = Query(5, ge=1, le=10),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[VocabResponse]:
	# Mỗi từ tốn 1 lần tra Ollama nên giới hạn số từ mỗi lần gọi.
	items = await import_from_errors(db, current_user.id, limit)
	return [vocab_response(item) for item in items]


@router.get("/due", response_model=list[VocabResponse])
async def get_due_vocab(
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[VocabResponse]:
	# Due list chỉ gồm từ đến hạn theo next_review_at của user hiện tại.
	items = await list_due_vocab(db, current_user.id)
	return [vocab_response(item) for item in items]


@router.post("/{vocab_item_id}/review", response_model=VocabReviewResponse)
async def review_vocab_item(
	vocab_item_id: UUID,
	request: VocabReviewRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> VocabReviewResponse:
	# Review được ràng buộc ownership trong service, tránh sửa state user khác.
	try:
		review = await review_vocab(db, current_user.id, vocab_item_id, request.quality)
	except ValueError as error:
		raise HTTPException(status_code=404, detail="resource_not_found") from error
	return VocabReviewResponse(
		next_review_at=review.next_review_at,
		ease_factor=float(review.ease_factor),
	)


@router.get("/{vocab_item_id}/word-family", response_model=WordFamilyResponse)
async def word_family(
	vocab_item_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> WordFamilyResponse:
	try:
		return WordFamilyResponse(**await get_word_family(db, current_user.id, vocab_item_id))
	except ValueError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{vocab_item_id}/check-sentence", response_model=VocabSentenceResponse)
async def check_sentence(
	vocab_item_id: UUID,
	request: VocabSentenceRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> VocabSentenceResponse:
	try:
		verdict = await check_vocab_sentence(db, current_user.id, vocab_item_id, request.sentence)
	except ValueError as error:
		code = str(error)
		raise HTTPException(status_code=422 if code == "term_not_used" else 404, detail=code) from error
	return VocabSentenceResponse(**verdict)
