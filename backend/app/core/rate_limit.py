import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

# ponytail: bộ nhớ trong 1 process; chạy nhiều worker/instance thì chuyển sang Redis.
_hits: dict[str, deque[float]] = defaultdict(deque)
WINDOW_SECONDS = 60


async def auth_rate_limit(request: Request) -> None:
	# Giới hạn theo IP + đường dẫn; AUTH_RATE_LIMIT_PER_MINUTE=0 thì tắt (mặc định, để dev/test không bị chặn).
	limit = get_settings().auth_rate_limit_per_minute
	if limit <= 0:
		return
	# Sau proxy (Render) IP thật nằm ở X-Forwarded-For.
	forwarded = request.headers.get("x-forwarded-for", "")
	ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
	hits = _hits[f"{ip}:{request.url.path}"]
	now = time.monotonic()
	while hits and now - hits[0] > WINDOW_SECONDS:
		hits.popleft()
	if len(hits) >= limit:
		raise HTTPException(
			status_code=status.HTTP_429_TOO_MANY_REQUESTS,
			detail="too_many_requests",
			headers={"Retry-After": str(WINDOW_SECONDS)},
		)
	hits.append(now)
