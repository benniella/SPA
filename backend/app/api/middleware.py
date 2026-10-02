"""CSRF protection for cookie-authenticated state-changing requests.

The session cookie is 'SameSite=Lax', which already stops a cross-site form post
from carrying it. This middleware adds the second layer: a signed-in caller must
echo the CSRF cookie into a header, so a request that is authenticated by
ambient browser state alone cannot change anything.

Only requests that are *cookie-authenticated* are checked. A request with no
session cookie has nothing a CSRF attack could ride on, and requiring a token for
sign-in and registration would break the very first request a client makes.
"""

from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class CsrfMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, cookie_name: str, header_name: str, enabled: bool) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._cookie_name = cookie_name
        self._header_name = header_name
        self._enabled = enabled

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self._enabled or request.method in SAFE_METHODS:
            return await call_next(request)

        # Not cookie-authenticated: the caller is either anonymous or presenting a
        # credential directly, neither of which a cross-site page can cause.
        session_cookie = request.cookies.get(self._session_cookie_name())
        if session_cookie is None:
            return await call_next(request)

        cookie_token = request.cookies.get(self._cookie_name)
        header_token = request.headers.get(self._header_name)
        if not cookie_token or not header_token:
            return _rejected()
        if not hmac.compare_digest(cookie_token, header_token):
            return _rejected()

        return await call_next(request)

    def _session_cookie_name(self) -> str:
        from app.core.config import get_settings

        return get_settings().session_cookie_name


def _rejected() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "error": {
                "code": "csrf_failed",
                "message": "The request could not be verified. Reload the page and try again.",
            }
        },
    )
