from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.auth import UpdateMeRequest, UserResponse


# Nhóm endpoint đọc/sửa thông tin user hiện tại.
router = APIRouter(prefix="/users", tags=["users"])


def _user_response(user: User) -> UserResponse:
	return UserResponse(
		id=str(user.id),
		email=user.email,
		target_level=user.target_level,
		timer_mode_enabled=user.timer_mode_enabled,
		created_at=user.created_at.isoformat(),
	)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
	# Dependency đã xác thực JWT; endpoint chỉ trả thông tin công khai của chính user đó.
	return _user_response(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
	request: UpdateMeRequest,
	current_user: User = Depends(get_current_user),
	db: AsyncSession = Depends(get_db),
) -> UserResponse:
	# Chỉ ghi field client thực sự gửi; target_level=null tường minh nghĩa là xóa mục tiêu.
	changed = False
	if "target_level" in request.model_fields_set:
		current_user.target_level = request.target_level
		changed = True
	if "timer_mode_enabled" in request.model_fields_set and request.timer_mode_enabled is not None:
		current_user.timer_mode_enabled = request.timer_mode_enabled
		changed = True
	if changed:
		await db.commit()
		await db.refresh(current_user)
	return _user_response(current_user)