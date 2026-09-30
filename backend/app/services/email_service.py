# Gửi email giao dịch qua Brevo HTTP API. BREVO_API_KEY rỗng -> chỉ log nội dung, để dev/test không cần tài khoản.
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body: str) -> None:
	# Lỗi gửi chỉ log, không raise: tránh lộ email có tồn tại hay không qua 500.
	settings = get_settings()
	if not settings.brevo_api_key:
		logger.warning("BREVO_API_KEY chưa cấu hình, email tới %s: %s\n%s", to, subject, body)
		return
	try:
		async with httpx.AsyncClient(timeout=15) as client:
			response = await client.post(
				"https://api.brevo.com/v3/smtp/email",
				headers={"api-key": settings.brevo_api_key},
				json={
					"sender": {"name": settings.mail_from_name, "email": settings.mail_from_email},
					"to": [{"email": to}],
					"subject": subject,
					"textContent": body,
				},
			)
			response.raise_for_status()
	except Exception:
		logger.exception("Gửi email tới %s thất bại", to)
