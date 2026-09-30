from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.core import rate_limit
from app.core.config import get_settings


def test_auth_rate_limit_blocks_after_limit(monkeypatch):
	monkeypatch.setattr(get_settings(), "auth_rate_limit_per_minute", 3)
	rate_limit._hits.clear()
	app = FastAPI()
	app.get("/x", dependencies=[Depends(rate_limit.auth_rate_limit)])(lambda: {})
	client = TestClient(app)
	assert [client.get("/x").status_code for _ in range(4)] == [200, 200, 200, 429]
	rate_limit._hits.clear()
