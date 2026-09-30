from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.models.base import Base
from app.models.auth_token import AuthToken  # noqa: F401
from app.models.refresh_token import RefreshToken
from app.models.user import User


config = context.config
settings = get_settings()
# Alembic đọc URL sync từ cùng Settings với ứng dụng, tránh lệch môi trường.
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
	fileConfig(config.config_file_name)

# Import model trước khi lấy metadata để autogenerate nhìn thấy đầy đủ bảng.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
	# Offline mode sinh SQL script mà không mở kết nối database.
	context.configure(
		url=settings.database_url_sync,
		target_metadata=target_metadata,
		literal_binds=True,
		dialect_opts={"paramstyle": "named"},
	)
	with context.begin_transaction():
		context.run_migrations()


def run_migrations_online() -> None:
	# Online mode mở kết nối sync psycopg để chạy migration trực tiếp.
	connectable = engine_from_config(
		config.get_section(config.config_ini_section, {}),
		prefix="sqlalchemy.",
		poolclass=pool.NullPool,
	)
	with connectable.connect() as connection:
		context.configure(connection=connection, target_metadata=target_metadata)
		with context.begin_transaction():
			context.run_migrations()


if context.is_offline_mode():
	# Alembic chọn nhánh dựa trên lệnh đang được gọi.
	run_migrations_offline()
else:
	run_migrations_online()
