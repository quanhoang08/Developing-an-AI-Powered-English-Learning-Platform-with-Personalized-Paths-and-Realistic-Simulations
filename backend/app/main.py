# Entry point FastAPI: khởi tạo app, gắn CORS và toàn bộ router nghiệp vụ dưới /api.
import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import InterfaceError, OperationalError, TimeoutError as PoolTimeoutError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.extension_scope import extension_scope_middleware
from app.core.errors import ai_http_error
from app.database import get_session_factory
from app.routers.activity import router as activity_router
from app.routers.adaptive import router as adaptive_router
from app.routers.auth import router as auth_router
from app.routers.economy import router as economy_router
from app.routers.extension import router as extension_router
from app.routers.gamification import router as gamification_router
from app.routers.games import router as games_router
from app.routers.grammar import router as grammar_router
from app.routers.listening import router as listening_router
from app.routers.movie_context import router as movie_context_router
from app.routers.notebook import router as notebook_router
from app.routers.pronunciation import router as pronunciation_router
from app.routers.classroom import router as classroom_router
from app.routers.social import diary_router, friends_router
from app.routers.readability import router as readability_router
from app.routers.reading import router as reading_router, stories_router
from app.routers.speaking import router as speaking_router
from app.routers.toeic import router as toeic_router
from app.routers.users import router as users_router
from app.services.llm_service import AIServiceError
from app.routers.vocab import router as vocab_router
from app.routers.writing import router as writing_router


logger = logging.getLogger(__name__)
settings = get_settings()
# Tạo FastAPI application và gắn metadata từ cấu hình môi trường.
app = FastAPI(
	title=settings.app_name,
	# Cố ý KHÔNG truyền debug=settings.debug: Starlette ưu tiên trang traceback debug hơn handler 500 bên dưới,
	# nên DEBUG=true (chỉ cần để log SQL) sẽ làm lộ traceback cho client.
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
app.include_router(economy_router, prefix="/api")
app.include_router(extension_router, prefix="/api")
app.include_router(gamification_router, prefix="/api")
app.include_router(games_router, prefix="/api")
app.include_router(grammar_router, prefix="/api")
app.include_router(listening_router, prefix="/api")
app.include_router(movie_context_router, prefix="/api")
app.include_router(notebook_router, prefix="/api")
app.include_router(pronunciation_router, prefix="/api")
app.include_router(readability_router, prefix="/api")
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


@app.exception_handler(OperationalError)
@app.exception_handler(InterfaceError)
@app.exception_handler(PoolTimeoutError)
async def handle_database_unavailable(request: Request, error: Exception):
	# DB sập/không kết nối được/hết pool: trả 503 JSON cùng dạng {"detail": {code, message, retryable}}
	# như lỗi AI, thay vì 500 kèm traceback (lộ host, SQL, đường dẫn nội bộ). Chi tiết chỉ ghi log server.
	logger.error("database unavailable on %s %s: %s", request.method, request.url.path, type(error).__name__)
	return JSONResponse(
		status_code=503,
		content={"detail": {"code": "database_unavailable", "message": "The service is temporarily unavailable. Try again in a moment.", "retryable": True}},
		headers={"Retry-After": "5"},
	)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, error: Exception):
	# Lưới an toàn cuối: lỗi không lường trước ra 500 JSON gọn, không bao giờ lộ traceback cho client
	# (app không bật debug của Starlette, xem FastAPI(...) ở trên). Traceback đầy đủ ở log.
	logger.exception("unhandled error on %s %s", request.method, request.url.path)
	return JSONResponse(
		status_code=500,
		content={"detail": {"code": "internal_error", "message": "Something went wrong on our side.", "retryable": False}},
	)


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
