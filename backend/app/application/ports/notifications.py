"""Transactional email and SMS delivery.

Delivery is a port so a use case never names a provider. A message that was not
actually accepted by a provider must not be reported as delivered: the
implementations raise 'EmailDeliveryError' rather than swallowing a failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class DeliveryError(Exception):
    """A provider refused or failed to accept the message.

    Deliberately not an 'AppError': the caller decides whether the failure is
    fatal to the request (a verification email that did not send leaves the
    account unverified, which the user must be told about) or merely logged.
    """


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str | None = None


@runtime_checkable
class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None:
        """Deliver a message, or raise 'DeliveryError'."""


@dataclass(frozen=True, slots=True)
class SmsMessage:
    to: str
    body: str


@runtime_checkable
class SmsSender(Protocol):
    async def send(self, message: SmsMessage) -> None:
        """Deliver a message, or raise 'DeliveryError'."""

    @property
    def configured(self) -> bool:
        """Whether a real delivery channel exists.

        The API answers '503' for a phone verification request when this is
        false, instead of claiming to have sent a code nobody will receive.
        """
