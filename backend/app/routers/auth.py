import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.rate_limit import auth_rate_limit
from app.database import get_db
from app.models.user import User
from app.core.config import get_settings
from app.schemas.auth import (
	EmailRequest,
	GoogleLoginRequest,
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
	login_with_google,
	register_user,
	request_email_flow,
	reset_password,
	rotate_refresh_token,
	send_verification_email,
	verify_email,
	verify_google_credential,
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


def _require_google_for_gmail(email: str) -> None:
	# Bật REQUIRE_GOOGLE_FOR_GMAIL: Gmail phải đi qua Google để chứng minh là chủ email (mặc định tắt để test).
	if get_settings().require_google_for_gmail and email.lower().endswith(("@gmail.com", "@googlemail.com")):
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="use_google_signin")


@router.get("/google/config")
async def google_config() -> dict[str, str | None]:
	# Frontend đọc client_id lúc chạy (không nhúng vào bundle); None = chưa cấu hình, ẩn nút Google.
	return {"client_id": get_settings().google_client_id or None}


@router.post("/google", response_model=TokenResponse)
async def google_login(
	request: GoogleLoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
	# Đăng nhập/đăng ký bằng Google: xác minh ID token với Google rồi cấp token pair như login thường.
	if not get_settings().google_client_id:
		raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="google_not_configured")
	try:
		email = await verify_google_credential(request.credential)
	except httpx.HTTPError as error:
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="google_unreachable") from error
	if email is None:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="invalid_google_credential",
			headers={"WWW-Authenticate": "Bearer"},
		)
	user = await login_with_google(db, email)
	access_token, refresh_token = await create_token_pair(db, user, request.client_type)
	return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
	request: RegisterRequest, background: BackgroundTasks, db: AsyncSession = Depends(get_db)
) -> UserResponse:
	# Endpoint đăng ký: validate schema trước, sau đó giao nghiệp vụ cho auth_service.
	_require_google_for_gmail(request.email)
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
	await send_verification_email(db, user, background)
	return user_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(
	request: LoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
	# Endpoint đăng nhập: xác thực user rồi trả access/refresh token pair.
	_require_google_for_gmail(request.email)
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
	# Nhập mã OTP 6 số gửi qua email để xác minh tài khoản; mã sai/hết hạn/quá 5 lần thử -> 400 invalid_or_expired_code.
	if not await verify_email(db, request.email, request.code):
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_or_expired_code")


@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
async def resend_verification(request: EmailRequest, background: BackgroundTasks, db: AsyncSession = Depends(get_db)) -> None:
	# Gửi lại mã xác minh email; luôn 204 dù email có tồn tại hay không (không lộ danh sách tài khoản).
	await request_email_flow(db, request.email, "verify_email", background)


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
async def forgot_password(request: EmailRequest, background: BackgroundTasks, db: AsyncSession = Depends(get_db)) -> None:
	# Bước 1 quên mật khẩu: gửi mã OTP đặt lại mật khẩu qua email; luôn 204 để không dò được email nào có tài khoản.
	await request_email_flow(db, request.email, "reset_password", background)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password_endpoint(request: ResetPasswordRequest, db: AsyncSession = Depends(get_db)) -> None:
	# Bước 2 quên mật khẩu: đúng OTP thì đổi mật khẩu và thu hồi mọi phiên cũ; sai/hết hạn -> 400 invalid_or_expired_code.
	if not await reset_password(db, request.email, request.code, request.new_password):
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_or_expired_code")
