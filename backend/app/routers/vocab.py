from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
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
)
from app.services.vocab_service import create_vocab_item, list_due_vocab, review_vocab


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
