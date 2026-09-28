# Frontend Architecture

Next.js (App Router) + React + TypeScript. This document explains the structure,
the boundaries, and the rules that make the structure hold.

---

## 1. Why Next.js with the App Router

**Next.js** because SPA needs both a rich interactive client (video scrubbing, a
pitch view, chart interactions) and server capabilities (auth callbacks, SSR of
report pages, image optimisation for video thumbnails) in one framework with one
deployment story.

**The App Router** — rather than the older Pages Router — for two reasons that
matter here:

1. **Route groups** let SPA define genuinely different shells for genuinely
   different audiences: '(marketing)', '(auth)', '(dashboard)'. The layout
   hierarchy is expressed in the filesystem, so a public marketing page cannot
   accidentally inherit dashboard chrome.
2. **React Server Components** let heavy read-only views (a season report, a
   squad list) render without shipping their data-fetching to the browser, while
   interactive views remain Client Components. SPA will have both.

**TypeScript in strict mode** because the application is data-heavy and the data
crosses a process boundary. 'strict' alone is not enough; 'tsconfig.json' also
enables 'noUncheckedIndexedAccess' (catches the out-of-bounds array read that
returns 'undefined' and is then '.map'ed) and 'noImplicitOverride'.

---

## 2. Directory structure

'''
frontend/src/
├── app/                      routing only — no business logic
│   ├── layout.tsx              root shell: HTML, fonts, tokens
│   ├── (marketing)/            public pages
│   ├── (auth)/                 sign-in, invitations
│   └── (dashboard)/            authenticated shell + pages
│
├── features/                 one directory per capability
│   ├── matches/  players/  teams/  videos/
│   ├── analysis/  tracking/  heatmaps/  reports/
│   └── README.md               the feature boundary rules
│
├── components/               shared, feature-agnostic
│   ├── ui/                     primitives (badge, placeholder, …)
│   ├── charts/                 chart wrappers          (reserved)
│   ├── video/                  video player wrapper    (reserved)
│   └── sports/                 pitch/formation visuals (reserved)
│
├── hooks/                    shared React hooks        (reserved)
├── lib/                      api client, config, errors, formatting
├── services/                 per-capability API modules
├── types/                    api.ts (contract) + domain.ts (vocabulary)
├── styles/                   design tokens
└── test/                     test setup
'''

---

## 3. The three rules

### Rule 1 — 'app/' contains routing, not logic

A file in 'app/' does one of three things: renders a layout, renders a page that
composes feature components, or handles a Next.js convention ('loading.tsx',
'error.tsx', 'not-found.tsx', route handlers).

Business logic, data-fetching hooks and UI detail live in 'features/'. The test:
can this file be understood in isolation without knowing SPA's domain? If not, it
is in the wrong place.

### Rule 2 — features may not import each other's internals

'''
features/videos/components/upload-dropzone.tsx   ← internal
features/videos/index.ts                          ← public surface

✅ import { UploadDropzone } from "@/features/videos"
❌ import { UploadDropzone } from "@/features/videos/components/upload-dropzone"
'''

Without this rule, 'features/' degrades into a second, worse 'components/' tree:
'matches' imports a helper from 'videos', 'analysis' imports both, and nothing can
be changed in isolation. The boundary is what delivers the benefit, not the
directory names.

Reuse across features has two legitimate paths:

* **Promote it.** If three features need the same thing and it is genuinely
  generic, it belongs in 'components/', 'hooks/' or 'lib/'.
* **Export it explicitly.** If it is capability-specific but another feature
  needs it, re-export from 'index.ts' so the dependency is visible and
  intentional rather than incidental.

### Rule 3 — all network I/O goes through 'lib/api-client.ts'

Feature code calls 'api.get(...)', never 'fetch(...)'.

Why this earns its keep:

| Concern                     | Without a choke point              | With one                   |
| --------------------------- | ---------------------------------- | -------------------------- |
| Adding auth headers         | Every call site                    | One file                   |
| Request tracing             | Every call site                    | One file                   |
| Timeout and abort policy    | Reimplemented per feature, wrongly | One implementation         |
| Error-shape normalisation   | 'if (msg.includes("not found"))'   | Typed 'ApiError.code'      |
| Swapping to a generated client | Rewrite every fetch              | Rewrite one module         |

**And the architecture rule this file embodies:** there is no database client in
the frontend, and there never will be. The data path is
Next.js → FastAPI → PostgreSQL. A browser-reachable tier holding database
credentials would duplicate business rules, make the API optional, and turn one
query bug into a cross-tenant leak.

---

## 4. State, data fetching and mutation

Phase 0 establishes the boundaries without choosing a library, because the right
choice depends on data volume and polling behaviour that is not measured yet.

**What exists now:** 'lib/api-client.ts' — a typed, abortable, timeout-bounded
fetch wrapper, plus 'ApiError'/'NetworkError' and 'fieldErrors' for validation
failures.

**What is deliberately absent:**

* a data-caching library (TanStack Query, SWR) — choosing by guesswork;
* global state management — nothing yet needs it;
* an auth context — there is no authentication.

**The pattern that will be needed first** is polling an analysis run until its
status is terminal. 'types/domain.ts' already defines 'isTerminalStatus' so that
logic has one home. The hook that uses it will live in 'hooks/' as
'usePollingQuery', because more than one feature will poll something.

---

## 5. The API contract

### Today: hand-written types, and this is a known limitation

'types/api.ts' mirrors the backend's Pydantic schemas by hand. It is deliberately
minimal — only the shapes the Phase 0 shell touches — because hand-maintaining a
full duplicate of the backend contract guarantees drift.

### Intended: generate from OpenAPI

The backend publishes 'http://localhost:8000/openapi.json', and FastAPI generates
it automatically. The intended flow:

'''
FastAPI schemas  →  /openapi.json  →  generated TypeScript client  →  frontend
'''

A 'npm run' script generating types into 'types/generated/' (git-tracked, so a
contract change appears in review as a diff) is the Phase 1 task. It makes the
contract single-sourced: the backend cannot change a response shape without the
frontend's types changing too.

### Error handling is already contract-shaped

The backend returns exactly one error envelope:

'''json
{ "error": { "code": "not_found", "message": "Video abc does not exist." } }
'''

'ApiError.code' is typed as 'ApiErrorCode | (string & {})'. The union gives
autocomplete for known codes; the open branch means a code added by a newer
backend does not break an older client. Clients switch on 'code', **never** on
'message' — messages are for humans and will change.

---

## 6. Design tokens rather than raw values

'styles/globals.css' defines semantic custom properties ('--background',
'--foreground', '--muted', '--primary', '--success', '--warning',
'--destructive') with light and dark values, mapped to Tailwind utilities via
'@theme inline'.

Components reference 'bg-background', never a hex literal. A theme change is then
one edit rather than a search-and-replace, and dark mode is not a second set of
class names.

**Tailwind itself is not installed in Phase 0.** Adding a full styling pipeline
before there is a component to style is premature. What is established is the
token layer and its vocabulary, so adding the build step later is configuration
rather than a rewrite.

---

## 7. Testing

**Vitest + Testing Library + jsdom.** Vitest shares Vite's transform pipeline, so
tests and application code resolve imports identically — a test that resolves
'@/' differently from the app is testing something other than what ships.

What is tested in Phase 0:

* 'lib/api-client.test.ts' — the error path, which is where a JSON API client
  actually goes wrong: a proxy returning HTML, a non-standard body, a network
  failure that is not a 'Response'. Each case has a specific user-visible
  consequence.
* 'types/domain.test.ts' — 'isTerminalStatus' decides whether polling continues.
  Getting it wrong means an infinite poll loop or a frozen progress bar, so it is
  worth testing despite being three lines.

**What is deliberately not tested:** rendered pages. Snapshot-testing a page
whose content is a placeholder asserts that the placeholder has not changed, which
is not a useful property.

---

## 8. Adding a feature: the intended shape

'''
features/heatmaps/
├── components/
│   ├── heatmap-canvas.tsx        rendering
│   └── heatmap-filters.tsx       controls
├── hooks/
│   └── use-heatmap-grid.ts       fetch + local state
├── services/
│   └── heatmaps.ts               api.get("/matches/{id}/heatmaps")
├── types.ts                      feature-local types
└── index.ts                      export the public surface

app/(dashboard)/matches/[matchId]/heatmaps/page.tsx   ← composes it
'''

The page is thin. Everything substantive is in the feature. If the heatmap view
is later rewritten, one directory changes and no other feature is affected —
which is the entire point.