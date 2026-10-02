"""Transactional email adapters.

Three real implementations: 'console' prints the message so local development
needs no provider, 'smtp' speaks SMTP to whatever relay the deployment uses, and
'resend' posts to the Resend HTTP API. All three raise on failure rather than
reporting a delivery that did not happen.
"""

from __future__ import annotations

import asyncio
import json
import logging
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage as SmtpMessage

from app.application.ports.notifications import DeliveryError, EmailMessage
from app.core.config import Settings

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"


class ConsoleEmailSender:
    """Prints the message instead of sending it.

    For local development only. The body is printed because it contains the
    verification or reset link a developer needs; that is exactly why this
    adapter must never be selected in production.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, message: EmailMessage) -> None:
        print(
            f"[email:console] to={message.to} subject={message.subject!r}\n{message.text}",
            flush=True,
        )


class SmtpEmailSender:
    """Sends over SMTP, blocking work moved off the event loop."""

    def __init__(self, settings: Settings) -> None:
        if not settings.smtp_host:
            raise DeliveryError("SMTP is selected but SPA_SMTP_HOST is empty.")
        self._settings = settings

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self._send_blocking, message)

    def _send_blocking(self, message: EmailMessage) -> None:
        settings = self._settings
        payload = SmtpMessage()
        payload["From"] = settings.email_from
        payload["To"] = message.to
        payload["Subject"] = message.subject
        if settings.email_reply_to:
            payload["Reply-To"] = settings.email_reply_to
        payload.set_content(message.text)
        if message.html:
            payload.add_alternative(message.html, subtype="html")

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
                if settings.smtp_starttls:
                    client.starttls()
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(payload)
        except (OSError, smtplib.SMTPException) as exc:
            raise DeliveryError(f"SMTP delivery failed: {type(exc).__name__}.") from exc


class ResendEmailSender:
    """Posts to the Resend HTTP API.

    Uses the standard library rather than the Resend SDK: one dependency fewer,
    and the request is three fields. The API key is sent in a header and is never
    logged, including on failure.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.resend_api_key:
            raise DeliveryError("Resend is selected but SPA_RESEND_API_KEY is empty.")
        self._settings = settings

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self._send_blocking, message)

    def _send_blocking(self, message: EmailMessage) -> None:
        settings = self._settings
        body = {
            "from": settings.email_from,
            "to": [message.to],
            "subject": message.subject,
            "text": message.text,
        }
        if message.html:
            body["html"] = message.html
        if settings.email_reply_to:
            body["reply_to"] = settings.email_reply_to

        request = urllib.request.Request(
            RESEND_ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                if response.status >= 300:
                    raise DeliveryError(f"Resend rejected the message ({response.status}).")
        except urllib.error.HTTPError as exc:
            raise DeliveryError(f"Resend rejected the message ({exc.code}).") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DeliveryError(f"Resend could not be reached: {type(exc).__name__}.") from exc
