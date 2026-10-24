from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user
from app.models.user import User
from app.utils import readability


# Hemingway-style: tách riêng router vì không đụng DB/LLM; cùng prefix /writing với router Writing.
router = APIRouter(prefix="/writing", tags=["writing"])


class ReadabilityRequest(BaseModel):
	text: str = Field(min_length=1, max_length=6000)


@router.post("/readability")
async def readability_check(request: ReadabilityRequest, current_user: User = Depends(get_current_user)) -> dict:
	return readability.analyze(request.text)
