# Chuyển AIServiceError (kèm mã nguyên nhân) thành HTTPException có thông điệp người dùng đọc được,
# thay vì 503 trống trơn. Body: {"detail": {"code", "message", "retryable"}}; frontend dùng `code` để
# chọn nút xử lý (thử lại / chuyển trang), `message` là câu dự phòng khi frontend chưa biết code đó.
from fastapi import HTTPException, status

from app.services.llm_service import AIServiceError

# code -> (HTTP status, thông điệp cho người học, có nên bấm "thử lại" không)
_AI_ERRORS: dict[str, tuple[int, str, bool]] = {
	"ollama_unreachable": (
		status.HTTP_503_SERVICE_UNAVAILABLE,
		"The local AI (Ollama) isn't running. Start Ollama, then try again.",
		True,
	),
	"ollama_model_missing": (
		status.HTTP_503_SERVICE_UNAVAILABLE,
		"The AI model isn't installed in Ollama yet. Pull the model, then try again.",
		False,
	),
	"ollama_timeout": (
		status.HTTP_504_GATEWAY_TIMEOUT,
		"The AI took too long to answer. Try again in a moment.",
		True,
	),
	"ai_quota_exceeded": (
		status.HTTP_429_TOO_MANY_REQUESTS,
		"The AI service has hit its usage limit for now. Try again later.",
		False,
	),
	"ai_bad_output": (
		status.HTTP_502_BAD_GATEWAY,
		"The AI gave an answer we couldn't use. Try again to get a fresh one.",
		True,
	),
	"ai_unavailable": (
		status.HTTP_503_SERVICE_UNAVAILABLE,
		"The AI service is temporarily unavailable. Try again in a moment.",
		True,
	),
}


def ai_http_error(error: AIServiceError) -> HTTPException:
	"""HTTPException tương ứng với nguyên nhân cụ thể của lỗi AI (mã lạ được coi như ai_unavailable)."""
	code = error.code if error.code in _AI_ERRORS else "ai_unavailable"
	http_status, message, retryable = _AI_ERRORS[code]
	return HTTPException(
		status_code=http_status,
		detail={"code": code, "message": message, "retryable": retryable},
	)
