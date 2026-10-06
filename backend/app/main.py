# Entry point FastAPI: khởi tạo app, gắn CORS và toàn bộ router nghiệp vụ dưới /api.
from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.extension_scope import extension_scope_middleware
from app.core.errors import ai_http_error
from app.database import get_session_factory
from app.routers.activity import router as activity_router
from app.routers.adaptive import router as adaptive_router
from app.routers.auth import router as auth_router
from app.routers.extension import router as extension_router
from app.routers.gamification import router as gamification_router
from app.routers.grammar import router as grammar_router
from app.routers.listening import router as listening_router
from app.routers.movie_context import router as movie_context_router
from app.routers.notebook import router as notebook_router
from app.routers.pronunciation import router as pronunciation_router
from app.routers.classroom import router as classroom_router
from app.routers.social import diary_router, friends_router
from app.routers.reading import router as reading_router, stories_router
from app.routers.speaking import router as speaking_router
from app.routers.toeic import router as toeic_router
from app.routers.users import router as users_router
from app.services.llm_service import AIServiceError
from app.routers.vocab import router as vocab_router
from app.routers.writing import router as writing_router


settings = get_settings()
# Tạo FastAPI application và gắn metadata từ cấu hình môi trường.
app = FastAPI(
	title=settings.app_name,
	debug=settings.debug,
)
# Thêm TRƯỚC CORS để CORS là lớp ngoài cùng: response 403 của scope vẫn có CORS header.
app.add_middleware(BaseHTTPMiddleware, dispatch=extension_scope_middleware)
# Cho phép frontend-reference en chạy ở port 3000 gọi API backend port 8000.
app.add_middleware(
	CORSMiddleware,
	allow_origins=settings.cors_origins,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)
# Các router nghiệp vụ đều dùng chung base path /api theo API spec.
app.include_router(activity_router, prefix="/api")
app.include_router(classroom_router, prefix="/api")
app.include_router(diary_router, prefix="/api")
app.include_router(friends_router, prefix="/api")
app.include_router(adaptive_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(extension_router, prefix="/api")
app.include_router(gamification_router, prefix="/api")
app.include_router(grammar_router, prefix="/api")
app.include_router(listening_router, prefix="/api")
app.include_router(movie_context_router, prefix="/api")
app.include_router(notebook_router, prefix="/api")
app.include_router(pronunciation_router, prefix="/api")
app.include_router(reading_router, prefix="/api")
app.include_router(stories_router, prefix="/api")
app.include_router(speaking_router, prefix="/api")
app.include_router(toeic_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(vocab_router, prefix="/api")
app.include_router(writing_router, prefix="/api")


@app.exception_handler(AIServiceError)
async def handle_ai_service_error(request: Request, error: AIServiceError):
	# Lưới an toàn: lỗi AI không router nào bắt vẫn ra JSON có mã + thông điệp (giữ CORS header)
	# thay vì 500 thô khiến browser chỉ thấy "Failed to fetch".
	return await http_exception_handler(request, ai_http_error(error))


@app.on_event("startup")
async def heal_orphaned_processing_documents() -> None:
	# Ingest chạy đồng bộ trong request upload (notebook_service.create_document), nên
	# status "processing" chỉ tồn tại trong lúc request đó đang chạy — nếu server crash/
	# restart giữa chừng, document bị bỏ lại vĩnh viễn ở "processing" (không request nào
	# còn sống để set "ready"/"failed"). Mọi document còn "processing" lúc app khởi động
	# lại chắc chắn là job mồ côi từ lần chạy trước, nên đánh dấu "failed" để user upload lại.
	async with get_session_factory()() as session:
		await session.execute(text("UPDATE documents SET status = 'failed' WHERE status = 'processing'"))
		await session.commit()


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
	# Endpoint nhẹ để Docker/orchestrator kiểm tra process API còn hoạt động.
	return {"status": "ok", "environment": settings.environment}
