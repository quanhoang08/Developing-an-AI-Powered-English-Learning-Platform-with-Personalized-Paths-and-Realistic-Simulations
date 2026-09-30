from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.rate_limit import auth_rate_limit
from app.database import get_db
from app.models.user import User
from app.core.config import get_settings
from app.schemas.auth import (
	EmailRequest,
	OtpRequest,
	LoginRequest,
	RefreshRequest,
	RegisterRequest,
	ResetPasswordRequest,
	TokenResponse,
	UserResponse,
)
from app.services.auth_service import (
	authenticate_user,
	create_token_pair,
	register_user,
	request_email_flow,
	reset_password,
	rotate_refresh_token,
	send_verification_email,
	verify_email,
)


# Nhóm endpoint xác thực; main.py mount router này dưới /api.
router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(auth_rate_limit)])


def user_response(user: User) -> UserResponse:
	# Chuyển ORM User thành DTO an toàn, loại bỏ password_hash khỏi response.
	return UserResponse(
		id=str(user.id),
		email=user.email,
		target_level=user.target_level,
		timer_mode_enabled=user.timer_mode_enabled,
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
	await send_verification_email(db, user)
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
	if get_settings().require_email_verification and user.email_verified_at is None:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="email_not_verified")
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


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
async def verify_email_endpoint(request: OtpRequest, db: AsyncSession = Depends(get_db)) -> None:
	if not await verify_email(db, request.email, request.code):
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_or_expired_code")


@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
async def resend_verification(request: EmailRequest, db: AsyncSession = Depends(get_db)) -> None:
	await request_email_flow(db, request.email, "verify_email")


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
async def forgot_password(request: EmailRequest, db: AsyncSession = Depends(get_db)) -> None:
	await request_email_flow(db, request.email, "reset_password")


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password_endpoint(request: ResetPasswordRequest, db: AsyncSession = Depends(get_db)) -> None:
	if not await reset_password(db, request.email, request.code, request.new_password):
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_or_expired_code")
