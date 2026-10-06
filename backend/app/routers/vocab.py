from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.vocab import VocabItem
from app.schemas.vocab import (
	ConfusableQuestion,
	ConfusableSubmitRequest,
	ConfusableSubmitResponse,
	MnemonicCreate,
	MnemonicItem,
	UnitImportRequest,
	UnitSummary,
	UnitImportResponse,
	VocabCreate,
	VocabResponse,
	VocabReviewRequest,
	VocabReviewResponse,
	VocabSentenceRequest,
	VocabSentenceResponse,
	WordFamilyResponse,
	WordlistAddRequest,
	WordlistCoverage,
	WordlistTextCoverage,
	WordlistTextRequest,
)
from app.services import confusable_service, mnemonic_service, wordlist_service
from app.services.vocab_service import (
	check_vocab_sentence,
	create_vocab_item,
	get_word_family,
	import_from_errors,
	import_unit,
	list_unit_words,
	list_units,
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


@router.post("/import-unit", response_model=UnitImportResponse)
async def vocab_import_unit(
	request: UnitImportRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> UnitImportResponse:
	result = await import_unit(db, current_user.id, request.lines, (request.unit or "").strip() or None)
	return UnitImportResponse(**{**result, "created": [vocab_response(i) for i in result["created"]]})


@router.get("/units", response_model=list[UnitSummary])
async def vocab_units(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
	return await list_units(db, current_user.id)


@router.get("/units/words", response_model=list[VocabResponse])
async def vocab_unit_words(
	unit: str = Query(min_length=1, max_length=100),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[VocabResponse]:
	return [vocab_response(item) for item in await list_unit_words(db, current_user.id, unit)]


@router.get("/confusables/quiz", response_model=list[ConfusableQuestion])
async def confusables_quiz(
	count: int = Query(8, ge=1, le=14),
	current_user: User = Depends(get_current_user),
) -> list[dict]:
	return confusable_service.make_quiz(count)


@router.post("/confusables/submit", response_model=ConfusableSubmitResponse)
async def confusables_submit(
	request: ConfusableSubmitRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> dict:
	try:
		return await confusable_service.grade_quiz(db, current_user.id, [a.model_dump() for a in request.answers])
	except ValueError as error:
		raise HTTPException(status_code=422, detail=str(error)) from error


_WORDLIST = Path(pattern="^(nawl|tsl)$")


@router.get("/wordlists/{name}/coverage", response_model=WordlistCoverage)
async def wordlist_coverage(
	name: str = _WORDLIST,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> dict:
	return await wordlist_service.coverage(db, current_user.id, name)


@router.post("/wordlists/{name}/text-coverage", response_model=WordlistTextCoverage)
async def wordlist_text_coverage(
	request: WordlistTextRequest,
	name: str = _WORDLIST,
	current_user: User = Depends(get_current_user),
) -> dict:
	return wordlist_service.text_coverage(name, request.text)


@router.post("/wordlists/{name}/add", response_model=list[VocabResponse])
async def wordlist_add(
	request: WordlistAddRequest,
	name: str = _WORDLIST,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[VocabResponse]:
	# Mỗi từ tốn 1 lần tra Ollama nên giới hạn 5 từ mỗi lần gọi (schema).
	items = await wordlist_service.add_words(db, current_user.id, name, request.words)
	return [vocab_response(item) for item in items]


@router.get("/topics")
async def vocab_topics(
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[dict]:
	return await wordlist_service.topic_overview(db, current_user.id)


@router.post("/topics/{topic_id}/add", response_model=list[VocabResponse])
async def add_vocab_topic(
	topic_id: str,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[VocabResponse]:
	try:
		items = await wordlist_service.add_topic_words(db, current_user.id, topic_id)
	except ValueError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error
	return [vocab_response(item) for item in items]


@router.get("/mnemonics", response_model=list[MnemonicItem])
async def list_mnemonics(
	term: str = Query(min_length=1, max_length=100),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[dict]:
	return await mnemonic_service.list_mnemonics(db, current_user.id, term)


@router.post("/mnemonics", status_code=status.HTTP_204_NO_CONTENT)
async def save_mnemonic(
	request: MnemonicCreate,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> None:
	await mnemonic_service.save_mnemonic(db, current_user.id, request.term, request.text.strip())


@router.post("/mnemonics/{mnemonic_id}/vote")
async def vote_mnemonic(
	mnemonic_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> dict:
	try:
		return {"voted": await mnemonic_service.toggle_vote(db, current_user.id, mnemonic_id)}
	except ValueError as error:
		code = str(error)
		raise HTTPException(status_code=409 if code == "cannot_vote_own" else 404, detail=code) from error


@router.post("/mnemonics/{mnemonic_id}/report", status_code=status.HTTP_204_NO_CONTENT)
async def report_mnemonic(
	mnemonic_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> None:
	try:
		await mnemonic_service.report_mnemonic(db, current_user.id, mnemonic_id)
	except ValueError as error:
		code = str(error)
		raise HTTPException(status_code=409 if code == "cannot_report_own" else 404, detail=code) from error


@router.delete("/mnemonics/{mnemonic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mnemonic(
	mnemonic_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> None:
	try:
		await mnemonic_service.delete_mnemonic(db, current_user.id, mnemonic_id)
	except ValueError as error:
		raise HTTPException(status_code=404, detail=str(error)) from error


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
