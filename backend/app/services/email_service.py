# Gửi email giao dịch: SMTP (Gmail) nếu có SMTP_USER/SMTP_PASSWORD, ngược lại Brevo HTTP API.
# Cả hai đều rỗng -> chỉ log nội dung, để dev/test không cần tài khoản.
import asyncio
import logging
import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _send_smtp(to: str, subject: str, body: str) -> None:
	settings = get_settings()
	msg = EmailMessage()
	msg["From"] = f"{settings.mail_from_name} <{settings.mail_from_email}>"
	msg["To"] = to
	msg["Subject"] = subject
	msg.set_content(body)
	with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
		server.starttls()
		server.login(settings.smtp_user, settings.smtp_password)
		server.send_message(msg)


async def send_email(to: str, subject: str, body: str) -> None:
	# Lỗi gửi chỉ log, không raise: tránh lộ email có tồn tại hay không qua 500.
	settings = get_settings()
	if settings.smtp_user and settings.smtp_password:
		try:
			await asyncio.to_thread(_send_smtp, to, subject, body)
		except Exception:
			logger.exception("Gửi email SMTP tới %s thất bại", to)
		return
	if not settings.brevo_api_key:
		logger.warning("Chưa cấu hình SMTP/BREVO_API_KEY, email tới %s: %s\n%s", to, subject, body)
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
			if response.is_error:
				# Brevo trả lý do cụ thể trong body (vd. "SMTP account is not yet activated").
				logger.error("Brevo từ chối email tới %s: %s %s", to, response.status_code, response.text)
	except Exception:
		logger.exception("Gửi email tới %s thất bại", to)
