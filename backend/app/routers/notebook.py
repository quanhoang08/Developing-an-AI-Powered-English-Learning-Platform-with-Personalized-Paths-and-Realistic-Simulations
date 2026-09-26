from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.notebook import Document, NotebookChatMessage, NotebookFolder
from app.models.user import User
from app.schemas.notebook import (
	ChatMessageCreate,
	ChatMessageResponse,
	ChatSendResponse,
	DocumentListResponse,
	DocumentResponse,
	DocumentUpdate,
	FolderCreate,
	FolderResponse,
)
from app.services.notebook_chat_service import list_messages, send_message
from app.services.notebook_service import (
	create_document,
	create_folder,
	delete_document,
	get_document,
	list_documents,
	list_folders,
	update_document,
)


# Endpoint Notebook: folder/document CRUD + upload (kích hoạt ingestion) + RAG Chat.
router = APIRouter(tags=["notebook"])


def folder_response(folder: NotebookFolder) -> FolderResponse:
	# Chuyển ORM folder sang response contract ổn định.
	return FolderResponse(id=folder.id, name=folder.name, created_at=folder.created_at)


def document_response(document: Document) -> DocumentResponse:
	# Chuyển ORM document sang DTO, không expose absolute storage path.
	return DocumentResponse(
		id=document.id,
		title=document.title,
		source_type=document.source_type,
		file_size_kb=document.file_size_kb,
		tags=document.tags,
		starred=document.starred,
		language=document.language,
		status=document.status,
		folder_id=document.folder_id,
		created_at=document.created_at,
	)


@router.post(
	"/notebook-folders",
	response_model=FolderResponse,
	status_code=status.HTTP_201_CREATED,
)
async def create_notebook_folder(
	request: FolderCreate,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> FolderResponse:
	# Owner được lấy từ JWT, không cho client tự truyền user_id.
	folder = await create_folder(db, current_user.id, request.name)
	return folder_response(folder)


@router.get("/notebook-folders", response_model=list[FolderResponse])
async def get_notebook_folders(
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[FolderResponse]:
	# Chỉ liệt kê folder của user hiện tại.
	folders = await list_folders(db, current_user.id)
	return [folder_response(folder) for folder in folders]


@router.post(
	"/documents",
	response_model=DocumentResponse,
	status_code=status.HTTP_201_CREATED,
)
async def upload_document(
	file: UploadFile = File(...),
	folder_id: UUID | None = Form(None),
	tags: list[str] | None = Form(None),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
	# Service validate extension và lưu document ở trạng thái processing.
	try:
		document = await create_document(db, current_user.id, file, folder_id, tags)
	except ValueError as error:
		status_code = (
			status.HTTP_404_NOT_FOUND
			if str(error) in {"folder_not_found"}
			else status.HTTP_400_BAD_REQUEST
		)
		raise HTTPException(status_code=status_code, detail=str(error)) from error
	return document_response(document)


@router.get("/documents", response_model=DocumentListResponse)
async def get_documents(
	folder_id: UUID | None = Query(None),
	starred: bool | None = Query(None),
	limit: int = Query(20, ge=1, le=100),
	offset: int = Query(0, ge=0),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
	# Pagination và filter đều được áp dụng sau ownership filter trong service.
	documents, total = await list_documents(
		db, current_user.id, folder_id, starred, limit, offset
	)
	return DocumentListResponse(
		items=[document_response(document) for document in documents],
		total=total,
		limit=limit,
		offset=offset,
	)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document_detail(
	document_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
	# Resource của user khác được trả 404 để không làm lộ sự tồn tại.
	try:
		document = await get_document(db, current_user.id, document_id)
	except ValueError as error:
		raise HTTPException(status_code=404, detail="resource_not_found") from error
	return document_response(document)


@router.patch("/documents/{document_id}", response_model=DocumentResponse)
async def patch_document(
	document_id: UUID,
	request: DocumentUpdate,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
	# Chỉ các field trong DocumentUpdate được phép thay đổi.
	try:
		document = await update_document(
			db,
			current_user.id,
			document_id,
			request.folder_id,
			request.tags,
			request.starred,
		)
	except ValueError as error:
		code = str(error)
		status_code = 404 if code in {"document_not_found", "folder_not_found"} else 400
		raise HTTPException(status_code=status_code, detail=code) from error
	return document_response(document)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document(
	document_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> None:
	# Xóa document và file upload, ownership được kiểm tra trong service.
	try:
		await delete_document(db, current_user.id, document_id)
	except ValueError as error:
		raise HTTPException(status_code=404, detail="resource_not_found") from error


_CHAT_ERROR_STATUS = {
	"document_not_found": status.HTTP_404_NOT_FOUND,
	"document_not_ready": status.HTTP_400_BAD_REQUEST,
}


def chat_message_response(message: NotebookChatMessage) -> ChatMessageResponse:
	# Chuyển ORM message sang DTO, dùng chung cho cả GET history và POST send.
	return ChatMessageResponse(
		id=message.id,
		role=message.role,
		content=message.content,
		sources=message.sources,
		created_at=message.created_at,
	)


@router.get("/documents/{document_id}/chat", response_model=list[ChatMessageResponse])
async def get_chat_history(
	document_id: UUID,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[ChatMessageResponse]:
	# Trả toàn bộ lịch sử chat của 1 document theo thứ tự thời gian, để client render lại.
	try:
		messages = await list_messages(db, current_user.id, document_id)
	except ValueError as error:
		code = str(error)
		raise HTTPException(status_code=_CHAT_ERROR_STATUS.get(code, 400), detail=code) from error
	return [chat_message_response(message) for message in messages]


@router.post(
	"/documents/{document_id}/chat",
	response_model=ChatSendResponse,
	status_code=status.HTTP_201_CREATED,
)
async def post_chat_message(
	document_id: UUID,
	request: ChatMessageCreate,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> ChatSendResponse:
	# RAG thật: tìm chunk liên quan bằng pgvector rồi gọi Gemini trả lời có trích dẫn.
	try:
		user_message, assistant_message = await send_message(
			db, current_user.id, document_id, request.message, provider=request.provider
		)
	except ValueError as error:
		code = str(error)
		raise HTTPException(status_code=_CHAT_ERROR_STATUS.get(code, 400), detail=code) from error
	return ChatSendResponse(
		user_message=chat_message_response(user_message),
		assistant_message=chat_message_response(assistant_message),
	)
