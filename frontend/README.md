# SPA Frontend

Next.js (App Router) + React + TypeScript application for **SPA — Sport
Performance Analysis**.

Its single job: present sports performance data to athletes, coaches, teams and
analysts.

---

## The architecture rule you must not break

'''
Next.js → FastAPI → PostgreSQL
'''

**The frontend never talks to PostgreSQL.** There is no database client here, no
connection string, and no server action that queries a database.

This is not a style preference. A browser-reachable tier holding database
credentials would:

- duplicate business rules in two languages that drift apart;
- make the FastAPI application optional, so tenancy enforcement becomes
  optional too;
- turn one query bug into a cross-tenant data leak.

The only data source is the versioned HTTP API, accessed through
'src/lib/api-client.ts'. CI enforces this
('scripts/check-architecture.sh').

---

## Structure

'''
src/
├── app/ routing only — no business logic
│ ├── layout.tsx root shell: HTML, metadata, global styles
│ ├── (marketing)/ public pages
│ ├── (auth)/ sign-in, invitations
│ └── (dashboard)/ authenticated shell + its pages
│
├── features/ one directory per capability
│ ├── matches/ players/ teams/ videos/
│ ├── analysis/ tracking/ heatmaps/ reports/
│ └── README.md the feature boundary rules — read this
│
├── components/ shared, feature-agnostic
│ ├── ui/ primitives (badge, placeholder)
│ ├── charts/ chart wrappers (Phase 1)
│ ├── video/ video player wrapper (Phase 1)
│ └── sports/ pitch/formation visuals (Phase 1)
│
├── hooks/ shared React hooks (Phase 1)
├── lib/ api client, config, errors
├── services/ per-capability API modules
├── types/ api.ts (contract) + domain.ts (vocabulary)
├── styles/ design tokens
└── test/ test setup
'''

### Three rules that make the structure hold

1. **'app/' contains routing, not logic.** A page composes feature components.
2. **Features may not import each other's internals.** Cross-feature reuse goes
   through 'index.ts' or is promoted to a shared layer. See
   ['src/features/README.md'](src/features/README.md).
3. **All network I/O goes through 'lib/api-client.ts'.** Feature code calls
   'api.get(...)', never 'fetch(...)'.

---

## Commands

From the repository root ('make help' lists everything):

'''bash
make frontend-install # npm install
make frontend-dev # dev server on :3000
make frontend-build # production build
make frontend-test # vitest
make frontend-lint # eslint
make frontend-fmt # prettier
make frontend-typecheck # tsc --noEmit
'''

Or from 'frontend/' directly: 'npm run dev', 'npm run check', etc.

---

## Configuration

'''bash
cp .env.example .env.local
'''

| Variable                         | Purpose                         |
| -------------------------------- | ------------------------------- |
| 'NEXT_PUBLIC_API_URL'            | Base URL of the FastAPI backend |
| 'NEXT_PUBLIC_API_VERSION_PREFIX' | '/api/v1'                       |

'lib/config.ts' **validates these at startup** and throws if one is missing. A
missing variable then fails immediately with a clear message instead of surfacing
as 'undefined' somewhere inside a fetch call.

Only 'NEXT_PUBLIC_'-prefixed variables reach the browser. Since they are inlined
at build time, **restart the dev server after changing one.**

---

## Status: Phase 0

The structure, boundaries, typed API client and test foundation exist. There are
**no product features**.

Specifically, the dashboard has **no metric tiles, no charts and no player
lists**. SPA has no analysis data yet, and inventing plausible-looking numbers is
the most damaging thing an early build can do: it makes an empty system look
finished, it gets demoed as though it works, and the lie eventually has to be
unwound.

What the Phase 0 shell _does_ prove is the data path, honestly: the dashboard's
status card calls the backend's readiness endpoint, which queries PostgreSQL. If
it shows **Operational**, the whole chain works.

### Known limitation

'src/types/api.ts' mirrors the backend's Pydantic schemas **by hand**. It is
deliberately minimal — only the shapes the shell touches — because
hand-maintaining a full duplicate guarantees drift.

The fix, scheduled for Phase 1, is to generate the client from the backend's
OpenAPI document so the contract has one source of truth. See
['../docs/api/README.md'](../docs/api/README.md) §5.

---

## Further reading

- ['../docs/architecture/frontend.md'](../docs/architecture/frontend.md) —
  the full reasoning behind this structure
- ['src/features/README.md'](src/features/README.md) — feature boundary rules
- ['../docs/architecture/overview.md'](../docs/architecture/overview.md) — the
  system as a whole
