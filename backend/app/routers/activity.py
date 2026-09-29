from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.gamification import RecentActivityItem, WeeklyActivityResponse
from app.services import activity_service, gamification_service


# Dashboard "This week, in minutes" + "Pick up where you left off" — không thuộc riêng 1 kỹ năng.
router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/weekly-summary", response_model=WeeklyActivityResponse)
async def get_weekly_summary(
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> WeeklyActivityResponse:
	summary = await gamification_service.get_weekly_activity(db, current_user.id)
	return WeeklyActivityResponse(timer_mode_enabled=current_user.timer_mode_enabled, **summary)


@router.get("/recent", response_model=list[RecentActivityItem])
async def get_recent_activity(
	limit: int = Query(default=5, ge=1, le=20),
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> list[RecentActivityItem]:
	items = await activity_service.get_recent(db, current_user.id, limit)
	return [RecentActivityItem(**item) for item in items]
