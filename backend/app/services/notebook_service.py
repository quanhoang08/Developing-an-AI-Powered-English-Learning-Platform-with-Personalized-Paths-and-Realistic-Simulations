# Business logic Notebook: CRUD folder/document + validate upload + kích hoạt ingestion.
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.notebook import Document, NotebookFolder
from app.services import rag_service


# Chỉ các định dạng đã được chốt trong phạm vi Lumina mới được upload.
ALLOWED_EXTENSIONS = {".docx", ".doc", ".pdf"}


def document_to_path(document_id: uuid.UUID, filename: str) -> Path:
	# Lưu theo UUID thay vì tên gốc để tránh path traversal và tên file trùng.
	settings = get_settings()
	root = Path(__file__).resolve().parents[2] / settings.storage_documents_dir
	root.mkdir(parents=True, exist_ok=True)
	return root / f"{document_id}{Path(filename).suffix.lower()}"


def validate_upload(filename: str | None) -> str:
	# Kiểm tra extension trước khi đọc file; MIME type từ client không được tin tuyệt đối.
	if not filename:
		raise ValueError("missing_filename")
	extension = Path(filename).suffix.lower()
	if extension not in ALLOWED_EXTENSIONS:
		raise ValueError("unsupported_file_type")
	return extension


async def create_folder(db: AsyncSession, user_id: uuid.UUID, name: str) -> NotebookFolder:
	# Folder luôn gắn với user hiện tại lấy từ JWT, không nhận owner từ request.
	folder = NotebookFolder(user_id=user_id, name=name.strip())
	db.add(folder)
	await db.commit()
	await db.refresh(folder)
	return folder


async def list_folders(db: AsyncSession, user_id: uuid.UUID) -> list[NotebookFolder]:
	# Chỉ trả các folder thuộc user hiện tại.
	result = await db.execute(
		select(NotebookFolder)
		.where(NotebookFolder.user_id == user_id)
		.order_by(NotebookFolder.created_at.desc())
	)
	return list(result.scalars().all())


async def create_document(
	db: AsyncSession,
	user_id: uuid.UUID,
	file: UploadFile,
	folder_id: uuid.UUID | None,
	tags: list[str] | None,
) -> Document:
	# Validate folder ownership trước khi ghi file để không tạo resource mồ côi.
	if folder_id is not None:
		folder = await db.scalar(
			select(NotebookFolder).where(
				NotebookFolder.id == folder_id,
				NotebookFolder.user_id == user_id,
			)
		)
		if folder is None:
			raise ValueError("folder_not_found")

	extension = validate_upload(file.filename)
	document_id = uuid.uuid4()
	path = document_to_path(document_id, file.filename or "document")
	content = await file.read()
	path.write_bytes(content)

	# Tài liệu mới bắt đầu ở processing; worker ingestion sẽ chuyển sang ready/failed.
	document = Document(
		id=document_id,
		user_id=user_id,
		folder_id=folder_id,
		title=Path(file.filename or "document").stem,
		source_type=extension.lstrip("."),
		file_path=str(path),
		file_size_kb=max(1, round(len(content) / 1024)),
		tags=tags or [],
		status="processing",
	)
	db.add(document)
	await db.commit()
	await db.refresh(document)

	# .docx/.doc/.pdf đều ingest thật ngay: extract + chunk + embed -> ready/failed.
	await rag_service.ingest_document(db, document)
	await db.refresh(document)
	return document


async def list_documents(
	db: AsyncSession,
	user_id: uuid.UUID,
	folder_id: uuid.UUID | None,
	starred: bool | None,
	limit: int,
	offset: int,
) -> tuple[list[Document], int]:
	# Xây query theo owner trước, sau đó áp dụng các bộ lọc tùy chọn.
	filters = [Document.user_id == user_id]
	if folder_id is not None:
		filters.append(Document.folder_id == folder_id)
	if starred is not None:
		filters.append(Document.starred == starred)

	total = await db.scalar(select(func.count()).select_from(Document).where(*filters)) or 0
	result = await db.execute(
		select(Document)
		.where(*filters)
		.order_by(Document.created_at.desc())
		.limit(limit)
		.offset(offset)
	)
	return list(result.scalars().all()), total


async def get_document(
	db: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID
) -> Document:
	# Truy vấn kèm user_id biến resource của user khác thành Not Found.
	document = await db.scalar(
		select(Document).where(Document.id == document_id, Document.user_id == user_id)
	)
	if document is None:
		raise ValueError("document_not_found")
	return document


async def update_document(
	db: AsyncSession,
	user_id: uuid.UUID,
	document_id: uuid.UUID,
	folder_id: uuid.UUID | None,
	tags: list[str] | None,
	starred: bool | None,
) -> Document:
	# Tải document theo ownership trước khi áp dụng PATCH.
	document = await get_document(db, user_id, document_id)
	if folder_id is not None:
		folder = await db.scalar(
			select(NotebookFolder).where(
				NotebookFolder.id == folder_id,
				NotebookFolder.user_id == user_id,
			)
		)
		if folder is None:
			raise ValueError("folder_not_found")
		document.folder_id = folder_id
	if tags is not None:
		document.tags = tags
	if starred is not None:
		document.starred = starred
	await db.commit()
	await db.refresh(document)
	return document


async def delete_document(
	db: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID
) -> None:
	# Xóa record và file vật lý, nhưng chỉ sau khi ownership đã được xác nhận.
	document = await get_document(db, user_id, document_id)
	if document.file_path:
		Path(document.file_path).unlink(missing_ok=True)
	await db.delete(document)
	await db.commit()
