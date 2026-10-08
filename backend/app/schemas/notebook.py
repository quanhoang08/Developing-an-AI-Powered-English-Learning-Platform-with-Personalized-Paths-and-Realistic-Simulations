from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FolderCreate(BaseModel):
	# Tên folder hiển thị cho user, không cho chuỗi rỗng hoặc quá dài.
	name: str = Field(min_length=1, max_length=100)


class FolderResponse(BaseModel):
	# DTO public của folder, không expose thông tin nội bộ ngoài owner id.
	id: UUID
	name: str
	created_at: datetime


class DocumentUpdate(BaseModel):
	# Các field được phép chỉnh sửa sau upload; file gốc không bị thay đổi qua PATCH.
	folder_id: UUID | None = None
	tags: list[str] | None = None
	starred: bool | None = None


class DocumentOverviewRequest(BaseModel):
	# Cùng quy ước provider như chat: "gemini" | "ollama" | None (mặc định settings).
	provider: str | None = None


class DocumentOverviewResponse(BaseModel):
	summary: str
	questions: list[str]


class DocumentResponse(BaseModel):
	# DTO dùng cho list/detail, phản ánh trạng thái xử lý để client polling.
	id: UUID
	title: str
	source_type: str
	file_size_kb: int | None
	tags: list[str] | None
	starred: bool
	language: str
	status: str
	folder_id: UUID | None
	created_at: datetime
	overview: DocumentOverviewResponse | None = None


class DocumentListResponse(BaseModel):
	# Contract phân trang thống nhất với api-spec.md.
	items: list[DocumentResponse]
	total: int
	limit: int
	offset: int


class ChatMessageCreate(BaseModel):
	# Payload gửi 1 câu hỏi RAG về document đang xem (kiểu NotebookLM).
	message: str = Field(min_length=1, max_length=4000)
	# "gemini" hoac "ollama" -- cho nguoi dung chon model tra loi chat. None -> mac dinh
	# gemini (xem llm_service.answer_grounded_question). De str thuong (khong Literal)
	# de khong phai sua enum moi khi them provider khac.
	provider: str | None = None


class ChatSource(BaseModel):
	# 1 trích dẫn chunk mà câu trả lời AI dựa vào — hiển thị dưới mỗi tin nhắn assistant.
	chunk_id: UUID
	excerpt: str


class ChatMessageResponse(BaseModel):
	# 1 dòng trong lịch sử chat; sources chỉ có giá trị khi role="assistant".
	id: UUID
	role: str
	content: str
	sources: list[ChatSource] | None
	created_at: datetime


class ChatSendResponse(BaseModel):
	# Trả về cả câu hỏi vừa lưu lẫn câu trả lời AI để client render ngay, không cần GET lại.
	user_message: ChatMessageResponse
	assistant_message: ChatMessageResponse
