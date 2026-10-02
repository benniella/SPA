"""Adapter selection from configuration.

The composition root for notification delivery. Use cases depend on the ports;
only this module knows which provider a deployment chose.
"""

from __future__ import annotations

from app.application.ports.notifications import EmailSender, SmsSender
from app.core.config import Settings


def build_email_sender(settings: Settings) -> EmailSender:
    from app.infrastructure.notifications.email import (
        ConsoleEmailSender,
        ResendEmailSender,
        SmtpEmailSender,
    )

    if settings.email_backend == "resend":
        return ResendEmailSender(settings)
    if settings.email_backend == "smtp":
        return SmtpEmailSender(settings)
    return ConsoleEmailSender(settings)


def build_sms_sender(settings: Settings) -> SmsSender:
    from app.infrastructure.notifications.sms import (
        ConsoleSmsSender,
        SmtpGatewaySmsSender,
        UnconfiguredSmsSender,
    )

    if settings.sms_backend == "console":
        return ConsoleSmsSender()
    if settings.sms_backend == "smtp_gateway":
        return SmtpGatewaySmsSender(settings)
    return UnconfiguredSmsSender()
