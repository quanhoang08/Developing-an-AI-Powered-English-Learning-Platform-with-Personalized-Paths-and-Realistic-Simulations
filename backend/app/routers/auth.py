from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import (
	authenticate_user,
	create_token_pair,
	register_user,
	rotate_refresh_token,
)


# Nhóm endpoint xác thực; main.py mount router này dưới /api.
router = APIRouter(prefix="/auth", tags=["auth"])


def user_response(user: User) -> UserResponse:
	# Chuyển ORM User thành DTO an toàn, loại bỏ password_hash khỏi response.
	return UserResponse(
		id=str(user.id),
		email=user.email,
		target_level=user.target_level,
		created_at=user.created_at.isoformat(),
	)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
	request: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> UserResponse:
	# Endpoint đăng ký: validate schema trước, sau đó giao nghiệp vụ cho auth_service.
	try:
		user = await register_user(
			db, request.email, request.password, request.target_level
		)
	except ValueError as error:
		if str(error) == "email_already_registered":
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="email_already_registered",
			) from error
		raise
	return user_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(
	request: LoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
	# Endpoint đăng nhập: xác thực user rồi trả access/refresh token pair.
	user = await authenticate_user(db, request.email, request.password)
	if user is None:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="invalid_credentials",
			headers={"WWW-Authenticate": "Bearer"},
		)
	access_token, refresh_token = await create_token_pair(db, user, request.client_type)
	return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
	request: RefreshRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
	# Đổi refresh token lấy cặp token mới (rotation); extension gọi route này khi access token hết hạn.
	pair = await rotate_refresh_token(db, request.refresh_token)
	if pair is None:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="invalid_refresh_token",
			headers={"WWW-Authenticate": "Bearer"},
		)
	return TokenResponse(access_token=pair[0], refresh_token=pair[1])
