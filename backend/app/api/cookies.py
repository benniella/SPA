"""Session cookie issuance and clearing.

The cookie is the one place a session token is exposed to the browser. It is
'HttpOnly' so script cannot read it, 'Secure' outside local development so it is
never sent over plain HTTP, and 'SameSite' so a cross-site form post cannot ride
on it. The CSRF cookie is deliberately readable by script: the double-submit
pattern requires the client to echo it into a header.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import Response

from app.core.config import Settings

CSRF_TOKEN_BYTES = 24


def set_session_cookie(response: Response, settings: Settings, *, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=int(timedelta(hours=settings.session_ttl_hours).total_seconds()),
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite_value,
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    """Expire the cookie.

    Clearing the browser's copy is a convenience; the authority is the revoked
    session row. A client that keeps the cookie still cannot use it.
    """
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite_value,
    )


def set_csrf_cookie(response: Response, settings: Settings, *, token: str) -> None:
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=int(timedelta(hours=settings.session_ttl_hours).total_seconds()),
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite_value,
        path="/",
    )


def clear_csrf_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite_value,
    )
