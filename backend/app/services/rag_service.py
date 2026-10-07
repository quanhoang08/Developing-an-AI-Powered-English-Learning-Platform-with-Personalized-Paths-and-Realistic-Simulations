# RAG orchestration: ingest tài liệu (extract+chunk+embed) và truy hồi chunk liên quan cho Chat.
import asyncio
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.models.notebook import Document, DocumentChunk
from app.services import llm_service
from app.utils.chunking import chunk_document
from app.utils.text_extraction import EXTRACTORS, extract_text

# Notebook chỉ nhận tài liệu văn bản: .docx, .doc, .pdf — trích text rồi chunk/embed.
INGESTIBLE_EXTENSIONS = set(EXTRACTORS)


def embedding_field() -> str:
	"""Cột vector tương ứng provider embedding: bge-m3 local → embedding_local (1024), Gemini → embedding (768)."""
	return "embedding_local" if get_settings().embedding_provider == "ollama" else "embedding"


async def ingest_document(db: AsyncSession, document: Document) -> None:
	"""Trích text, chunk, sinh embedding và lưu document_chunks; cập nhật status.

	Chạy đồng bộ ngay trong request upload — chấp nhận được ở quy mô khóa luận (tài liệu
	ngắn, không cần hàng đợi background job riêng).
	"""
	extension = Path(document.file_path or "").suffix.lower()
	if extension not in INGESTIBLE_EXTENSIONS:
		# Định dạng chưa có pipeline: giữ nguyên "processing", không phải lỗi.
		return

	try:
		# Parse docx/pdf/antiword là việc đồng bộ — đẩy sang threadpool để không chặn event loop khi file lớn.
		text = await run_in_threadpool(extract_text, document.file_path)
		# Chia theo câu + chồng lấp (thay cho cắt cứng theo số từ) — chọn theo experiments/run_retrieval.py.
		settings = get_settings()
		chunks = chunk_document(
			text, settings.chunk_strategy, settings.chunk_max_words, settings.chunk_overlap_sentences
		)
		if not chunks:
			document.status = "failed"
			await db.commit()
			return

		# Gọi embedding song song thay vì tuần tự từng chunk — với tài liệu nhiều chunk,
		# chờ lần lượt (mỗi lần ~2-3s) là lý do chính khiến upload "mãi chưa xong".
		embeddings = await asyncio.gather(
			*(llm_service.embed_text(chunk_content, is_query=False) for chunk_content in chunks)
		)
		field = embedding_field()
		for index, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
			db.add(
				DocumentChunk(
					document_id=document.id,
					chunk_index=index,
					content=chunk_content,
					token_count=len(chunk_content.split()),
					**{field: embedding},
				)
			)
		document.status = "ready"
		await db.commit()
	except Exception:
		document.status = "failed"
		await db.commit()


async def retrieve_relevant_chunks(
	db: AsyncSession, document_id: uuid.UUID, query: str, top_k: int = 5
) -> list[DocumentChunk]:
	"""Tìm top_k chunk gần nghĩa nhất với query bằng cosine distance trên pgvector."""
	query_embedding = await llm_service.embed_text(query, is_query=True)
	column = getattr(DocumentChunk, embedding_field())
	result = await db.execute(
		select(DocumentChunk)
		.where(DocumentChunk.document_id == document_id, column.is_not(None))
		.order_by(column.cosine_distance(query_embedding))
		.limit(top_k)
	)
	return list(result.scalars().all())
