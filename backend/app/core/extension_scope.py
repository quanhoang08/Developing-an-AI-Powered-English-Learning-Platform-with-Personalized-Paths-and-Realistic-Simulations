# Middleware giới hạn phạm vi route của token extension (api-spec.md mục 0.2, AUTH-007/007b).
# Allow-list tĩnh, không có cột DB riêng: chỉ đọc claim client_type trong JWT.
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from app.core.security import get_token_client_type

_ALLOWED_EXACT = {"/api/reading/lookup", "/api/vocab"}
_ALLOWED_PREFIXES = ("/api/extension/",)


def is_extension_allowed(path: str) -> bool:
	# True nếu đường dẫn nằm trong allow-list của extension (khớp chính xác hoặc theo prefix); bỏ dấu "/" cuối trước khi so.
	path = path.rstrip("/") or "/"
	return path in _ALLOWED_EXACT or path.startswith(_ALLOWED_PREFIXES)


async def extension_scope_middleware(request: Request, call_next: RequestResponseEndpoint):
	# Chạy trước mọi route: token extension gọi ngoài allow-list -> 403 extension_token_scope_denied; còn lại cho đi tiếp.
	# Không có Bearer (login/register/refresh/preflight/health) -> để route tự xử lý.
	scheme, _, token = request.headers.get("authorization", "").partition(" ")
	if (
		scheme.lower() == "bearer"
		and get_token_client_type(token) == "extension"
		and not is_extension_allowed(request.url.path)
	):
		return JSONResponse(
			status_code=403,
			content={"detail": {"error_code": "extension_token_scope_denied"}},
		)
	return await call_next(request)
