from fastapi import APIRouter, Depends, HTTPException, WebSocket
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user
from app.models.user import User
from app.routers.reading import lookup
from app.schemas.reading import LookupResponse
from app.services import caption_service


# Route riêng cho Browser Extension (api-spec.md mục 8): tra từ trên trang web bất kỳ. Dùng lại
# đúng handler của Reading (cùng lookup_term/Ollama, cùng auth) — không có luồng tra từ thứ hai.
router = APIRouter(prefix="/extension", tags=["extension"])
router.add_api_route("/lookup", lookup, methods=["POST"], response_model=LookupResponse)


@router.websocket("/captions")
async def tab_captions(websocket: WebSocket) -> None:
	# Phụ đề trực tiếp cho âm thanh của 1 tab trình duyệt (extension): cùng giao thức và xác thực với /speaking/captions.
	await caption_service.run_captions(websocket)


class TranslateRequest(BaseModel):
	text: str = Field(min_length=1, max_length=300)


class TranslateResponse(BaseModel):
	translation: str


@router.post("/translate", response_model=TranslateResponse)
async def translate(
	request: TranslateRequest,
	_current_user: User = Depends(get_current_user),
) -> TranslateResponse:
	# Dịch 1 dòng phụ đề (YouTube) sang tiếng Việt bằng Ollama, cùng hàm với phụ đề trực tiếp; Ollama tắt → 503 để extension
	# lùi về MyMemory.
	try:
		return TranslateResponse(translation=await caption_service.translate_to_vi(request.text))
	except Exception as error:  # noqa: BLE001 — Ollama tắt/thiếu model/quá chậm đều là "không dịch được lúc này"
		raise HTTPException(status_code=503, detail="translate_unavailable") from error
