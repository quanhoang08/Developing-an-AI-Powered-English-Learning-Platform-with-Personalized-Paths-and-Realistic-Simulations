import pytest

from app.core import rate_limit
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _no_auth_rate_limit():
	# Test tích hợp đăng ký rất nhiều tài khoản từ cùng 1 IP, chạm giới hạn đăng nhập/đăng ký (429) của môi
	# trường chạy thật. Tắt giới hạn khi test; test_auth_rate_limit tự bật lại bằng monkeypatch.
	settings = get_settings()
	original = settings.auth_rate_limit_per_minute
	settings.auth_rate_limit_per_minute = 0
	rate_limit._hits.clear()
	yield
	settings.auth_rate_limit_per_minute = original
