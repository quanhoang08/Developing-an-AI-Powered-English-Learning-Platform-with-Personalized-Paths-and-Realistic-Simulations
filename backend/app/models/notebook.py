import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NotebookFolder(Base):
	"""Folder riêng của user để phân loại tài liệu Notebook."""

	__tablename__ = "notebook_folders"

	# UUID giúp resource không lộ thứ tự tạo và khớp schema PostgreSQL hiện tại.
	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	# Mọi truy vấn folder phải ràng buộc user_id từ JWT ở service/router.
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	name: Mapped[str] = mapped_column(String(100))
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)


class Document(Base):
	"""Tài liệu DOCX/DOC/PDF được user upload vào Notebook."""

	__tablename__ = "documents"

	# Định danh document được dùng lại bởi Reading, Listening và Writing.
	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	folder_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("notebook_folders.id", ondelete="SET NULL"), nullable=True
	)
	title: Mapped[str] = mapped_column(String(255))
	# Service chỉ nhận docx/doc/pdf dù DB cũ còn record audio lịch sử.
	source_type: Mapped[str] = mapped_column(String(20))
	source_url: Mapped[str] = mapped_column(Text, nullable=True)
	file_path: Mapped[str] = mapped_column(Text, nullable=True)
	file_size_kb: Mapped[int] = mapped_column(Integer, nullable=True)
	tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
	starred: Mapped[bool] = mapped_column(Boolean, default=False)
	language: Mapped[str] = mapped_column(String(10), default="en")
	status: Mapped[str] = mapped_column(String(20), default="processing")
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)


class DocumentChunk(Base):
	"""Một đoạn nội dung đã chunk, là nguồn citation của Classic Reading."""

	__tablename__ = "document_chunks"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	document_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE")
	)
	chunk_index: Mapped[int] = mapped_column(Integer)
	content: Mapped[str] = mapped_column(Text)
	# 768 chiều khớp models/gemini-embedding-001 với output_dimensionality=768 (llm_service).
	embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=True)
	# 1024 chiều khớp bge-m3 chạy local qua Ollama (EMBEDDING_PROVIDER=ollama) — cột riêng nên cùng tồn
	# tại với embedding Gemini cũ, không phải xóa dữ liệu khi đổi provider.
	embedding_local: Mapped[list[float]] = mapped_column(Vector(1024), nullable=True)
	page_or_line_ref: Mapped[str] = mapped_column(String(50), nullable=True)
	token_count: Mapped[int] = mapped_column(Integer, nullable=True)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)


class NotebookChatMessage(Base):
	"""Một tin nhắn trong luồng chat RAG (kiểu NotebookLM) gắn với 1 document."""

	__tablename__ = "notebook_chat_messages"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
	)
	document_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE")
	)
	user_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
	)
	role: Mapped[str] = mapped_column(String(10))
	content: Mapped[str] = mapped_column(Text)
	# Chỉ set cho role='assistant' — danh sách {chunk_id, excerpt} để hiển thị trích dẫn.
	sources: Mapped[list[dict]] = mapped_column(JSONB, nullable=True)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), server_default=text("now()")
	)
