# Quản lý SQLAlchemy async engine/session dùng chung cho toàn bộ router qua Depends(get_db).
import asyncio
import sys
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


# Psycopg async không hỗ trợ ProactorEventLoop trên Windows.
# Dùng SelectorEventLoop để tương thích với Python 3.14 và FastAPI TestClient.
if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
	# Khởi tạo engine lười: import app không cần kết nối DB hoặc import driver trước.
	# Engine chỉ được tạo khi endpoint thực sự cần mở database session.
	global _session_factory
	if _session_factory is None:
		settings = get_settings()
		engine = create_async_engine(
			settings.database_url,
			echo=settings.debug,
			pool_pre_ping=True,
		)
		_session_factory = async_sessionmaker(
			bind=engine,
			class_=AsyncSession,
			expire_on_commit=False,
		)
	return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
	# Dependency dùng chung cho các router; session tự đóng sau khi request kết thúc.
	async with get_session_factory()() as session:
		yield session
