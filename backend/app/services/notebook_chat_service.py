# Business logic RAG Chat (Notebook): lịch sử hội thoại + gửi câu hỏi mới (retrieve + generate).
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notebook import Document, DocumentChunk, NotebookChatMessage
from app.services import llm_service, rag_service


async def _get_owned_ready_document(
	db: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID
) -> Document:
	# Helper dùng chung: chỉ cho chat khi document thuộc user và đã ingest xong (status=ready).
	document = await db.scalar(
		select(Document).where(Document.id == document_id, Document.user_id == user_id)
	)
	if document is None:
		raise ValueError("document_not_found")
	if document.status != "ready":
		raise ValueError("document_not_ready")
	return document


async def list_chunk_texts(
	db: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID
) -> list[str]:
	# Nội dung tab Content: các chunk đã ingest theo thứ tự gốc (cùng ownership check với chat).
	await _get_owned_ready_document(db, user_id, document_id)
	result = await db.execute(
		select(DocumentChunk.content)
		.where(DocumentChunk.document_id == document_id)
		.order_by(DocumentChunk.chunk_index.asc())
	)
	return list(result.scalars().all())


async def generate_overview(
	db: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID, provider: str | None
) -> dict:
	# Sinh tóm tắt rồi lưu vào documents.overview để tải lại trang vẫn còn (Regenerate ghi đè).
	document = await _get_owned_ready_document(db, user_id, document_id)
	chunks = await list_chunk_texts(db, user_id, document_id)
	overview = await llm_service.summarize_document("\n\n".join(chunks), provider)
	document.overview = overview
	await db.commit()
	return overview


async def list_messages(
	db: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID
) -> list[NotebookChatMessage]:
	# Ownership check trước để không lộ nội dung chat của tài liệu user khác.
	await _get_owned_ready_document(db, user_id, document_id)
	result = await db.execute(
		select(NotebookChatMessage)
		.where(NotebookChatMessage.document_id == document_id)
		.order_by(NotebookChatMessage.created_at.asc())
	)
	return list(result.scalars().all())


async def send_message(
	db: AsyncSession,
	user_id: uuid.UUID,
	document_id: uuid.UUID,
	message: str,
	provider: str | None = None,
) -> tuple[NotebookChatMessage, NotebookChatMessage]:
	"""Lưu câu hỏi user, chạy RAG (retrieve + generate) rồi lưu câu trả lời — trả cả 2 dòng."""
	await _get_owned_ready_document(db, user_id, document_id)

	history = await list_messages(db, user_id, document_id)
	history_payload = [{"role": item.role, "content": item.content} for item in history]

	user_message = NotebookChatMessage(
		document_id=document_id, user_id=user_id, role="user", content=message
	)
	db.add(user_message)
	await db.flush()

	relevant_chunks = await rag_service.retrieve_relevant_chunks(db, document_id, message)
	answer = await llm_service.answer_grounded_question(
		[chunk.content for chunk in relevant_chunks], message, history_payload, provider=provider
	)
	sources = [
		{"chunk_id": str(chunk.id), "excerpt": chunk.content[:200]} for chunk in relevant_chunks
	]

	assistant_message = NotebookChatMessage(
		document_id=document_id,
		user_id=user_id,
		role="assistant",
		content=answer,
		sources=sources,
	)
	db.add(assistant_message)
	await db.commit()
	await db.refresh(user_message)
	await db.refresh(assistant_message)
	return user_message, assistant_message
