# FastAPI dependency dùng ở mọi endpoint riêng tư để xác thực JWT và nạp user hiện tại.
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User


# FastAPI dùng scheme này để lấy Bearer token từ Authorization header.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
	token: str = Depends(oauth2_scheme),
	db: AsyncSession = Depends(get_db),
) -> User:
	# Dependency bảo vệ các endpoint riêng tư: decode JWT rồi tải user từ database.
	user_id = decode_access_token(token)
	if user_id is None:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="invalid_token",
			headers={"WWW-Authenticate": "Bearer"},
		)

	# Luôn truy vấn theo id lấy từ token, không nhận user_id từ request body/query.
	result = await db.execute(select(User).where(User.id == user_id))
	user = result.scalar_one_or_none()
	if user is None:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="invalid_token",
			headers={"WWW-Authenticate": "Bearer"},
		)
	return user
