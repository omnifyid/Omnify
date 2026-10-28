import html

import httpx

from app.config import settings


class EmailSendError(RuntimeError):
    pass


async def send_password_reset_email(email: str, reset_url: str) -> None:
    if not settings.resend_api_key:
        raise EmailSendError("RESEND_API_KEY is not configured")

    safe_reset_url = html.escape(reset_url, quote=True)
    payload = {
        "from": settings.resend_from_email,
        "to": [email],
        "subject": "Reset your Kasir password",
        "html": (
            "<p>You requested a password reset for your Kasir account.</p>"
            f'<p><a href="{safe_reset_url}">Reset your password</a></p>'
            "<p>This link expires in 30 minutes. If you did not request it, ignore this email.</p>"
        ),
        "text": (
            "You requested a password reset for your Kasir account.\n\n"
            f"Reset your password: {reset_url}\n\n"
            "This link expires in 30 minutes. If you did not request it, ignore this email."
        ),
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json=payload,
        )

    if response.status_code >= 400:
        raise EmailSendError(f"Resend failed with status {response.status_code}")
