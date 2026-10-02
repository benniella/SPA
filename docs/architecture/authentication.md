# Authentication and Account Security

Phase 9 replaced the development identity header with server-controlled sessions.
This document describes the resulting model and the configuration it depends on.

---

## 1. Identity is server-side

The browser holds one opaque value: the session cookie. It contains no identity,
no claims and nothing the client can alter meaningfully. The `sessions` row that
the cookie's hash resolves to is the authority on who the caller is.

`GET /auth/me` is the only way the frontend learns who is signed in. Nothing is
inferred from browser storage — the frontend keeps a workspace *selection* in
`localStorage`, but whether that selection is usable is decided by the API.

```
Request
  ↓
session cookie → hash (keyed with SPA_SESSION_SECRET) → sessions row
  ↓
user row → account_status must permit authentication
  ↓
authenticated identity → organization membership → authorization
```

Every request re-checks the account state, so suspending an account stops its
existing sessions immediately rather than when a cookie expires.

### The development identity header

`SPA_DEV_IDENTITY_HEADER` enables an `x-spa-user-id` header outside production.
It exists so the Phase 0–8 integration suite can act as a chosen user without a
credential exchange. It can never be enabled in production: the dependency checks
`settings.is_production` independently of the flag, so no configuration value
turns it on there.

---

## 2. Sessions

| Property | Value |
|---|---|
| Storage | `sessions` table; the token is stored as a keyed hash |
| Cookie | `HttpOnly`, `SameSite` from config, `Secure` outside `local` |
| Absolute expiry | `SPA_SESSION_TTL_HOURS` (default 14 days) |
| Idle timeout | `SPA_SESSION_IDLE_TIMEOUT_HOURS` (default 7 days) |
| Revocation | A database write; a retained cookie stops working |

`Secure` is derived from the environment rather than configured, because a
`Secure` cookie is never sent over plain-HTTP local development and a
non-`Secure` cookie in production is a credential leak on any downgrade.

Logout revokes the row. A client that keeps its cookie still cannot use it.

### CSRF

The session cookie is `SameSite=Lax`, which already blocks a cross-site form
post from carrying it. `CsrfMiddleware` adds the second layer: a
*cookie-authenticated* mutating request must echo the `spa_csrf` cookie into the
`X-CSRF-Token` header. Requests with no session cookie are not checked, because
sign-in and registration have nothing a CSRF attack could ride on.

---

## 3. Credentials

Passwords are hashed with PBKDF2 (`app/infrastructure/security/passwords.py`)
behind the `PasswordHasher` port. The domain never sees a plaintext password.

Verification, reset, email-change and OTP secrets are stored **hashed** with
`SPA_SESSION_SECRET`. A database read cannot be replayed as a valid link or code.

| Challenge | Table | Lifetime |
|---|---|---|
| Email verification | `security_challenges` | `SPA_EMAIL_VERIFICATION_TTL_HOURS` |
| Email change | `security_challenges` | `SPA_EMAIL_CHANGE_TTL_HOURS` |
| Password reset | `security_challenges` | `SPA_PASSWORD_RESET_TTL_HOURS` |
| Account recovery | `security_challenges` + `otp_challenges` | `SPA_RECOVERY_TTL_HOURS` |
| Phone verification | `otp_challenges` | `SPA_OTP_TTL_MINUTES` |

All are single-use: consuming one sets `consumed_at`, and issuing a replacement
consumes any outstanding challenge of the same kind first.

### Account lifecycle

```
PENDING_VERIFICATION ──verify──▶ ACTIVE ──suspend──▶ SUSPENDED
                                  │                     │
                                  └──deactivate──▶ DEACTIVATED
```

`PENDING_VERIFICATION` and `ACTIVE` may authenticate; `SUSPENDED` and
`DEACTIVATED` may not. A user can sign in before verifying, but the account is
marked unverified until the link is opened. Accounts are never hard-deleted to
implement suspension, so audit records keep their referents.

---

## 4. Email and SMS delivery

Delivery sits behind `EmailSender` and `SmsSender` ports. No use case names a
provider.

```
application use case
  ↓
EmailSender / SmsSender port
  ↓
console | SMTP | Resend          console | gateway
```

`SPA_EMAIL_BACKEND` selects `console` (prints; the local default), `smtp` or
`resend`. `SPA_RESEND_API_KEY` is required for Resend and is never logged.

`SPA_SMS_BACKEND` defaults to `none`, which means no provider is configured. The
phone endpoints then answer `503` rather than claiming to have sent a code. This
is deliberate: reporting a delivery that did not happen would be worse than
reporting that none is available.

A delivery failure raises `EmailDeliveryError` and surfaces as `502`. The account
state is left unchanged, so a retry is safe.

---

## 5. Rate limiting

Authentication endpoints are rate limited per caller and, where it matters, per
account. `SPA_RATE_LIMIT_STORE=keydb` shares counters across processes;
`process` is correct for a single process. The limiter fails closed: an
unreachable store raises rather than silently disabling the limit.

| Endpoint | Limit setting |
|---|---|
| `POST /auth/login` | `SPA_RATE_LIMIT_LOGIN_PER_MINUTE` + per-account |
| `POST /auth/register` | `SPA_RATE_LIMIT_REGISTER_PER_HOUR` |
| `POST /auth/forgot-password`, `/auth/reset-password` | `SPA_RATE_LIMIT_PASSWORD_RESET_PER_HOUR` |
| `POST /auth/resend-verification` | `SPA_RATE_LIMIT_RESEND_VERIFICATION_PER_HOUR` |
| `POST /account/phone/*` | `SPA_RATE_LIMIT_PHONE_PER_HOUR` |

---

## 6. Account enumeration

Registration, sign-in, forgot-password and resend-verification answer
identically whether or not an address has an account, and a failed sign-in is
indistinguishable from an unknown one. This is the property that makes those
endpoints safe to expose, and it is covered by tests.

---

## 7. Security events

`security_events` is append-only. There is no update or delete path in the
repository, and the API exposes only a read of the caller's own events. The
vocabulary lives in `SecurityEventType`.

Events never carry secret material: a record that a password was reset is useful,
the token that reset it is not.

---

## 8. Local development

The defaults in `backend/.env.example` need no external service:

* `SPA_EMAIL_BACKEND=console` prints verification and reset links to the server
  log, so the flows can be walked end to end without a mail provider.
* `SPA_SMS_BACKEND=none` means phone verification answers `503`.
* `SPA_RATE_LIMIT_STORE=process` needs no KeyDB.
* `SPA_DEV_IDENTITY_HEADER=true` keeps the Phase 0–8 integration suite working.

---

## 9. Production requirements

* `SPA_ENVIRONMENT=production` — this is what turns on `Secure` cookies, the
  trusted-host middleware and CSRF enforcement, and what disables the
  development identity header.
* `SPA_SESSION_SECRET` — at least 32 random characters. Rotating it invalidates
  every session and every outstanding challenge.
* `SPA_DATABASE_URL`.
* `SPA_EMAIL_BACKEND=resend` with `SPA_RESEND_API_KEY` and `SPA_EMAIL_FROM`.
* `SPA_CORS_ORIGINS` and `SPA_ALLOWED_HOSTS` set to the real hosts.
* `SPA_RATE_LIMIT_STORE=keydb` when more than one process serves traffic.
* `SPA_APP_BASE_URL` — the origin used to build verification and reset links.