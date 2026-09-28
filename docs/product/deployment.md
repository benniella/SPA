# Deployment

How SPA is deployed. Only the frontend runs on Vercel; the API, the worker and
PostgreSQL are separate services, because a serverless function cannot host a
long-running worker or a durable queue consumer.

---

## 1. What runs where

| Component     | Platform                        | Why                                              |
| ------------- | ------------------------------- | ------------------------------------------------ |
| Next.js       | Vercel                          | Built for it; preview deployments per pull request |
| FastAPI       | A long-running host (container) | Needs a persistent process and a database pool    |
| Worker        | The same host as the API        | Consumes the KeyDB queue; long-running by design  |
| PostgreSQL    | A managed instance              | Durable state; not serverless-compatible          |
| KeyDB / Redis | A managed instance              | The job queue and realtime fan-out                |

The frontend reaches the API over HTTP at `NEXT_PUBLIC_API_URL`. It never talks
to PostgreSQL. See [`../architecture/frontend.md`](../architecture/frontend.md).

---

## 2. Vercel project setup

`frontend/vercel.json` holds the build settings and the security headers, so the
project is configured by the repository rather than by clicking through the
dashboard.

| Setting          | Value                                              |
| ---------------- | -------------------------------------------------- |
| Root directory   | `frontend`                                         |
| Framework        | Next.js (detected)                                 |
| Build command    | `npm run build`                                    |
| Install command  | `npm ci`                                           |
| Node.js version  | 20.9+ (`package.json` `engines`)                   |

`npm ci` rather than `npm install`: it installs exactly the lockfile and fails
on drift, so a build cannot silently resolve a different dependency tree than
the one that was tested.

### Environment variables

Set these in the Vercel project settings, per environment.

| Variable                       | Required | Value                                                     |
| ------------------------------ | -------- | --------------------------------------------------------- |
| `NEXT_PUBLIC_API_URL`          | yes      | Public origin of the API, e.g. `https://api.spanalysis.com` |
| `NEXT_PUBLIC_API_VERSION_PREFIX` | no     | Defaults to `/api/v1`                                      |
| `NEXT_PUBLIC_WS_URL`           | no       | Realtime origin, e.g. `wss://ws.spanalysis.com`             |
| `NEXT_PUBLIC_SITE_URL`         | no       | Deployed origin, for canonical and Open Graph URLs          |

Every variable is public by definition: `NEXT_PUBLIC_` values are inlined into
the browser bundle at build time. **No server secret may be given that prefix.**
The API's `SPA_SESSION_SECRET`, database URL and KeyDB URL belong to the API
host's environment, never to this project.

`NEXT_PUBLIC_API_URL` is validated at module load (`src/lib/config.ts`), so a
missing value fails the build rather than producing a page that throws on its
first request.

### Preview deployments

Vercel builds every pull request. A preview URL points at whatever
`NEXT_PUBLIC_API_URL` the *Preview* environment defines — set it to a staging API
rather than production, so a preview cannot write to real data.

---

## 3. Headers

`vercel.json` sets the headers the application cannot set for itself on static
assets:

* `X-Content-Type-Options: nosniff` — stops a mislabelled asset being sniffed
  into a script;
* `X-Frame-Options: DENY` — the application is never framed;
* `Referrer-Policy: strict-origin-when-cross-origin` — a cross-origin request
  does not leak the full path;
* `Permissions-Policy` — camera, microphone, geolocation and interest cohorts
  are all off; SPA uses none of them;
* `Strict-Transport-Security` — HTTPS only.

The API sets its own CORS and session-cookie policy; those are not duplicated
here. `SPA_CORS_ORIGINS` on the API must include the frontend origin, or the
browser will block every request.

---

## 4. Deploying

'''bash
# One-off: link the repository to the Vercel project.
cd frontend && vercel link

# Preview deployment.
vercel

# Production deployment.
vercel --prod
'''

A deployment is correct once the API is reachable at `NEXT_PUBLIC_API_URL` with
CORS allowing the deployed frontend origin. Verifying the frontend without that
is verifying a page that will fail on its first fetch.

---

## 5. What is not configured here

* **The API is not deployed from this repository's Vercel project.** It needs a
  persistent process, a database connection pool and the worker alongside it.
* **No serverless function calls the database.** The architecture rule in
  [`../architecture/frontend.md`](../architecture/frontend.md) §3 is what makes
  the frontend deployable to a static-plus-edge platform at all.
* **No secrets are committed.** `frontend/vercel.json` contains none, and
  `scripts/check-architecture.sh` fails the build if an `.env` file is tracked.