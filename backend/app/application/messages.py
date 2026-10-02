"""Message bodies for transactional email.

Composed here rather than in a use case so a template change never touches
authentication logic, and so no template can accidentally interpolate a secret
beyond the single link or code it exists to carry.
"""

from __future__ import annotations

from app.application.ports.notifications import EmailMessage


def verification_email(*, to: str, display_name: str, link: str) -> EmailMessage:
    return EmailMessage(
        to=to,
        subject="Verify your SPA email address",
        text=(
            f"Hello {display_name},\n\n"
            "Confirm this address to finish setting up your SPA account:\n\n"
            f"{link}\n\n"
            "If you did not create an SPA account, ignore this message.\n"
        ),
    )


def password_reset_email(*, to: str, display_name: str, link: str) -> EmailMessage:
    return EmailMessage(
        to=to,
        subject="Reset your SPA password",
        text=(
            f"Hello {display_name},\n\n"
            "Use this link to choose a new password:\n\n"
            f"{link}\n\n"
            "If you did not ask for this, ignore this message. Your current password "
            "still works.\n"
        ),
    )


def email_change_email(*, to: str, display_name: str, link: str) -> EmailMessage:
    return EmailMessage(
        to=to,
        subject="Confirm your new SPA email address",
        text=(
            f"Hello {display_name},\n\n"
            "Confirm this address to make it the email address on your SPA account:\n\n"
            f"{link}\n\n"
            "Until you confirm it, your account keeps its current address.\n"
        ),
    )


def email_changed_notice(*, to: str, display_name: str, new_email: str) -> EmailMessage:
    """Warn the *old* address that the account is moving.

    Sent to the address being replaced, because that is the mailbox whose owner
    still has an interest in a change they may not have made.
    """
    return EmailMessage(
        to=to,
        subject="Your SPA email address was changed",
        text=(
            f"Hello {display_name},\n\n"
            f"The email address on your SPA account was changed to {new_email}.\n\n"
            "If this was not you, sign in and reset your password immediately.\n"
        ),
    )


def security_notice(*, to: str, display_name: str, summary: str) -> EmailMessage:
    return EmailMessage(
        to=to,
        subject="Security notice for your SPA account",
        text=f"Hello {display_name},\n\n{summary}\n",
    )
def admin_invitation_email(*, to: str, role: str, link: str) -> EmailMessage:
    return EmailMessage(
        to=to,
        subject="You have been invited to administer SPA",
        text=(
            "You have been invited to the SPA platform administration team.\n\n"
            f"Invited role: {role}\n\n"
            "Accept the invitation and set up your second factor here:\n\n"
            f"{link}\n\n"
            "This link can be used once and expires. If you were not expecting it, "
            "ignore this message.\n"
        ),
    )
