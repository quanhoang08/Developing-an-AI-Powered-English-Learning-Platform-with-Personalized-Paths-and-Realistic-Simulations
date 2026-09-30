from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
	# Payload đăng ký; EmailStr và Field validate input trước khi vào service/database.
	email: EmailStr
	password: str = Field(min_length=8, max_length=128)
	target_level: str | None = Field(default=None, min_length=2, max_length=10)


class LoginRequest(BaseModel):
	# Payload đăng nhập tối thiểu gồm email và mật khẩu.
	email: EmailStr
	password: str = Field(min_length=1, max_length=128)
	# "extension" chỉ THU HẸP quyền (allow-list route), nên client tự khai báo là an toàn.
	client_type: Literal["web", "extension"] = "web"


class RefreshRequest(BaseModel):
	# Payload dùng để đổi refresh token lấy access token mới.
	refresh_token: str = Field(min_length=1)


class EmailRequest(BaseModel):
	email: EmailStr


class OtpRequest(EmailRequest):
	code: str = Field(pattern=r"^\d{6}$")


class ResetPasswordRequest(OtpRequest):
	new_password: str = Field(min_length=8, max_length=128)


class UpdateMeRequest(BaseModel):
	# PATCH /users/me: target_level (api-spec.md mục 1) + timer_mode_enabled (bật/tắt "chế độ bấm
	# giờ" cho Dashboard "This week, in minutes", mục 3.16 lumina_context.md).
	target_level: str | None = Field(default=None, min_length=2, max_length=10)
	timer_mode_enabled: bool | None = None


class UserResponse(BaseModel):
	# DTO công khai; không trả password_hash hoặc dữ liệu bảo mật nội bộ.
	id: str
	email: EmailStr
	target_level: str | None
	timer_mode_enabled: bool
	created_at: str


class TokenResponse(BaseModel):
	# Hợp đồng response chuẩn cho các luồng cấp token.
	access_token: str
	refresh_token: str
	token_type: str = "bearer"
