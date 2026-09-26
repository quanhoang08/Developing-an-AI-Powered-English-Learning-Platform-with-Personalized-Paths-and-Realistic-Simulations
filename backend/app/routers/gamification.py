from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.gamification import SkillProgressResponse, StreakResponse
from app.services import gamification_service


router = APIRouter(tags=["gamification"])


@router.get("/streaks", response_model=StreakResponse)
async def get_streaks(
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> StreakResponse:
	# Chỉ đọc số liệu của chính user trong JWT, không nhận user_id từ query.
	return StreakResponse(**await gamification_service.get_summary(db, current_user.id))


@router.get("/skills", response_model=list[SkillProgressResponse])
async def get_skills(
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[SkillProgressResponse]:
	# Chỉ trả kỹ năng đã có điểm; user mới học trả danh sách rỗng.
	rows = await gamification_service.list_skill_progress(db, current_user.id)
	return [
		SkillProgressResponse(
			skill_name=row.skill_name,
			score=float(row.score) if row.score is not None else None,
			cefr_level=row.cefr_level,
			updated_at=row.updated_at,
		)
		for row in rows
	]
