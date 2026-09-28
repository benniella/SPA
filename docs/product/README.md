# Product Documentation

Documents in this directory describe SPA from the product side: what it does, who
it is for, and how to work on it.

| Document                                  | Covers                                                     |
| ----------------------------------------- | ---------------------------------------------------------- |
| ['local-development.md'](local-development.md) | Setup, commands, testing, troubleshooting, editor config |

---

## What SPA is

**Turn sports video into performance data.**

SPA is an AI-powered sports performance analysis platform. It turns sports video
into structured performance data for athletes, coaches, teams and analysts.

### Who it is for

| User          | Wants                                                            |
| ------------- | ---------------------------------------------------------------- |
| **Coach**     | "How far did we run, where did we lose shape, who faded?"         |
| **Analyst**   | Underlying data: distances, sprint counts, positions, exports     |
| **Athlete**   | Their own numbers over time                                        |
| **Team / club** | A shared workspace across matches, squads and seasons           |

The coach is the primary user. A performance analyst will read the raw numbers;
a coach wants the answer. Both are served by the same data, presented
differently — which is why metrics are relational rows and not a rendered
picture.

---

## Capability roadmap

Listed so that "planned" is distinguishable from "built". **Nothing below is
implemented in Phase 0.**

| Capability                     | Status | Blocked by                                    |
| ------------------------------ | ------ | --------------------------------------------- |
| Sports video upload            | Schema and API contract exist; no bytes processed | Worker (Phase 1)              |
| Match management               | Domain and schema exist; no UI                     | Frontend feature work          |
| Teams                          | Domain and schema exist; no UI                     | Frontend feature work          |
| Players                        | Domain and schema exist; no UI                     | Frontend feature work          |
| Player tracking                | Not started                                        | Detector + tracker choice      |
| Object / player detection      | Not started                                        | Footage characteristics        |
| Movement analysis              | Not started                                        | Tracking output                |
| Heatmaps                       | Model exists; nothing computes them                | Tracking + pitch calibration   |
| Team shape analysis            | Model exists; nothing computes it                  | Tracking + pitch calibration   |
| Performance metrics            | Relational model exists; nothing writes to it      | Tracking + metric definitions  |
| Workload / intensity analysis  | Model exists; nothing computes it                  | Tracking + zone thresholds     |
| Reports                        | Domain and schema exist; no generation             | Real metrics to report on      |
| AI-assisted insights           | Not started                                        | Everything above               |

### Why the schema runs ahead of the features

The tables for tracking datasets, metrics and heatmaps exist even though nothing
computes them. That is deliberate: they encode decisions (metrics are relational,
calibration is provenance, tracking output is versioned) that would be expensive
to change later — and they let the async contract be tested against real
storage today.

What they do **not** do is pretend. No table is populated with generated data, no
endpoint returns a fabricated metric, and no screen displays a number that was
not computed from footage.

---

## Product principles that shaped the architecture

### 1. Honest empty states

A foundation phase is full of "not built yet". The repository uses an explicit
'StatusPlaceholder' component so that state is unambiguous, and it never fills
space with plausible-looking fake data.

Inventing analytics is the most damaging thing an early build can do: it makes an
empty system look finished, it gets demoed as though it works, and someone
eventually has to explain that the numbers were never real.

### 2. Numbers must be reproducible

A metric is only useful if you can answer "where did this come from?":

* every metric records the analysis run that produced it ('analysis_run_id');
* every run records its pipeline and model versions ('pipeline_spec',
  'stage_results');
* every tracking dataset records its calibration and model provenance;
* every metric records its 'definition_version'.

Without these, re-running the pipeline silently changes historical numbers and a
season review becomes unrepeatable.

### 3. Partial results beat no results

A multi-stage pipeline can produce valid tracking data while a later stage fails.
'partially_succeeded' is a distinct outcome so that hours of expensive, usable
work are not discarded because one downstream step broke — and so a coach knows
that some numbers are available and others are not.

### 4. Squad history must not be rewritten

Players transfer. Analysis of a past match must resolve the squad as it actually
was, not as it is today. This is why membership is a dated record rather than a
column — a wrong answer here would quietly corrupt every historical comparison.

### 5. Costs are paid when they are real

No microservices, no Kubernetes, no Kafka, no event sourcing, no CQRS — not
because they are bad, but because each has an operational cost paid on every
working day in exchange for a benefit SPA has not yet measured. The boundaries
that would allow them to be adopted later exist; the complexity does not.

See ['../architecture/overview.md'](../architecture/overview.md) §8 for the
decisions that are explicitly still open.

---

## Phase 0 — what this repository contains

Foundation only. Deliverables:

1. Repository structure across 'frontend/', 'backend/', 'ml/', 'docs/',
   'scripts/', '.github/'
2. FastAPI application with four layers and enforced domain boundaries
3. PostgreSQL schema with a hand-written, reversible initial migration
4. Nine domains with entities, invariants and use cases
5. Async video-processing interfaces ('JobDispatcher', 'VideoStorage') with
   working local implementations
6. Next.js App Router structure with three route groups and real feature
   boundaries
7. A typed, abortable API client with contract-shaped error handling
8. Tooling: Ruff, mypy, pytest, ESLint, Prettier, TypeScript strict, Vitest
9. 139 passing tests (120 backend, 19 frontend), 13 of them against real
   PostgreSQL
10. Documentation: architecture, API, and local development

**What is deliberately absent:** every product feature, all computer vision, all
analytics, and any number that was not computed from real data.

### Next phase

Recommended Phase 1 work, in order:

1. **Authentication** — unblocks every per-user feature and is on the critical
   path for anything real.
2. **Worker extraction** — Celery + Redis, a 'worker' service in compose, and one
   job handler that ingests a real video and probes it.
3. **S3 storage adapter** — one new class implementing the existing port.
4. **Generated API client** — removes the largest contract risk in the frontend.
5. **Field-level permissions** — once the role model is settled.
6. **Then** computer vision, once footage characteristics are measured.

Items 1–4 are all foundation work. Starting on detection before them would mean
discovering, later, that the pipeline's interfaces do not fit the way the product
actually schedules and reports work.