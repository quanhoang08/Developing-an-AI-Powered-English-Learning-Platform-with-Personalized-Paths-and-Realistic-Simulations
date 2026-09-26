from fastapi import APIRouter

from app.routers.reading import lookup
from app.schemas.reading import LookupResponse


# Route riêng cho Browser Extension (api-spec.md mục 8): tra từ trên trang web bất kỳ. Dùng lại
# đúng handler của Reading (cùng lookup_term/Ollama, cùng auth) — không có luồng tra từ thứ hai.
router = APIRouter(prefix="/extension", tags=["extension"])
router.add_api_route("/lookup", lookup, methods=["POST"], response_model=LookupResponse)
