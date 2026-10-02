"""SMS delivery adapters.

No SMS provider is integrated in this phase. 'UnconfiguredSmsSender' is a real
implementation of the port that reports itself as unconfigured, so the phone
endpoints answer '503' rather than claiming to have sent a code that never
existed. Adding a provider means adding one class here and one configuration
value; nothing in the application layer changes.
"""

from __future__ import annotations

from app.application.ports.notifications import DeliveryError, SmsMessage
from app.core.config import Settings


class UnconfiguredSmsSender:
    """The honest default: no provider, so no delivery is possible."""

    configured = False

    async def send(self, message: SmsMessage) -> None:
        raise DeliveryError("No SMS provider is configured for this deployment.")


class ConsoleSmsSender:
    """Prints the message instead of sending it.

    Local development only, and selected explicitly. It reports itself as
    configured because a developer who chose it does see the code.
    """

    configured = True

    async def send(self, message: SmsMessage) -> None:
        print(f"[sms:console] to={message.to}\n{message.body}", flush=True)


class SmtpGatewaySmsSender:
    """Sends an SMS through a carrier email-to-SMS gateway.

    A real delivery channel that needs no SMS vendor: the carrier accepts an
    email addressed to the number at its gateway domain. It reports itself as
    configured only when a gateway domain is set, because without one there is
    nowhere to send.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        from app.infrastructure.notifications.email import SmtpEmailSender

        self._email = SmtpEmailSender(settings)

    @property
    def configured(self) -> bool:
        return bool(self._settings.sms_gateway_domain)

    async def send(self, message: SmsMessage) -> None:
        if not self.configured:
            raise DeliveryError("No SMS gateway domain is configured.")
        from app.application.ports.notifications import EmailMessage

        digits = "".join(character for character in message.to if character.isdigit())
        await self._email.send(
            EmailMessage(
                to=f"{digits}@{self._settings.sms_gateway_domain}",
                subject="",
                text=message.body,
            )
        )
