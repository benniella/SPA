# Database Architecture

PostgreSQL is SPA's primary relational database. This document describes the
entity model, the JSONB policy, the indexing strategy and the migration
workflow.

---

## 1. Why PostgreSQL

SPA's data is overwhelmingly relational. Organizations contain teams; teams
contain players; matches reference two teams and contain videos; videos produce
analysis runs; runs produce metrics. Foreign keys, unique constraints and
transactions are exactly the right tools.

**Rejected: MongoDB or a document store as primary.** Analysis *metadata* is
genuinely open-ended, and JSONB handles that well in PostgreSQL. But making the
whole model unstructured would turn "largest distance covered this season" into a
collection scan and an application-side sort. The relational core is what is
being queried; it is not a constraint to work around.

**Rejected: SQLite.** Cannot be the primary architecture. SPA needs concurrent
writers (API and workers), 'ON DELETE CASCADE', JSONB, 'uuid' columns and
partial indexes. Testing against SQLite would mean the production-specific
behaviour is never exercised — which is exactly why the integration tests run
against real PostgreSQL and are the only place the schema is truly verified.

**Version:** PostgreSQL 16, via 'postgres:16-alpine'. Collation is pinned
('--locale=C') so index ordering is stable across machines.

---

## 2. The entity model

'''
                    ┌───────────────┐
                    │ organizations │  ← tenancy boundary
                    └───────┬───────┘
        ┌───────────────────┼───────────────────┬──────────────┐
        │                   │                   │              │
┌───────▼──────┐   ┌────────▼───────┐  ┌────────▼──────┐  ┌────▼────┐
│    teams     │   │    players     │  │    matches    │  │ videos  │
└───────┬──────┘   └────────┬───────┘  └────────┬──────┘  └────┬────┘
        │                   │                   │              │
        │  ┌────────────────▼──────────┐        │              │
        └──►   team_memberships        │        │              │
           │  (dated registration)      │        │              │
           └───────────────────────────┘        │              │
                                                │              │
                                    ┌───────────▼──────────────▼───┐
                                    │        analysis_runs          │
                                    └───────────┬──────────────────┘
                                                │
                        ┌───────────────────────┼───────────────────────┐
                        │                       │                       │
              ┌─────────▼─────────┐  ┌──────────▼──────────┐  ┌────────▼──────┐
              │ tracking_datasets │  │ performance_metrics │  │ heatmap_grids │
              └───────────────────┘  └─────────────────────┘  └───────────────┘

users ──► organization_memberships ──► organizations
reports ──► organizations (+ optional match/team scope, created_by user)
'''

### Every table, and why it exists

| Table                     | Purpose                                                        |
| ------------------------- | -------------------------------------------------------------- |
| 'organizations'           | The tenancy boundary. Everything else scopes to one.           |
| 'users'                   | Identity. Organization-independent — an analyst can span clubs. |
| 'organization_memberships'| Binds user ↔ organization with a role. Unique per pair.        |
| 'teams'                   | A squad: name, slug (unique per org), sport, season.           |
| 'players'                 | An athlete, owned by the organization, **not** by a team.       |
| 'team_memberships'        | Dated player ↔ team registration. See §3.                       |
| 'matches'                 | The organising concept. Teams by id **or** by name.            |
| 'videos'                  | Source media: pointer, lifecycle state, technical characteristics. |
| 'analysis_runs'           | One execution of the pipeline over one video. The async contract. |
| 'tracking_datasets'       | Versioned, immutable trajectory output.                        |
| 'track_metrics'           | Phase 6 derived metrics, one row per track and metric name.    |
| 'performance_metrics'     | Relational metric rows. See §4.                                |
| 'heatmap_grids'           | A spatial density grid per player/team/period.                 |
| 'reports'                 | Generated snapshot documents.                                  |

---

## 3. Relationship decisions worth explaining

### Players belong to organizations, not teams

A 'players.team_id' column would be simpler. It would also be wrong.

Players transfer. If the player row pointed at a team, a mid-season transfer
would either rewrite history — last season's report would suddenly show the new
squad — or orphan the performance data attached to the player.

'team_memberships' carries a **validity window**:

'''
team_memberships(id, team_id, player_id, joined_on, left_on, shirt_number)
CHECK (left_on IS NULL OR left_on >= joined_on)
'''

So "who played for the Under-18s on 2024-09-15" is a SQL predicate:

'''sql
WHERE joined_on <= :on_date
  AND (left_on IS NULL OR left_on >= :on_date)
'''

This is applied in the repository ('SqlPlayerRepository.list_for_team'), not in
Python, so it stays cheap as squads and seasons accumulate. The API exposes it as
'GET /players?team_id=…&on_date=…'.

**Shirt number lives on the membership, not the player.** A player changes
number between seasons and squads, and a number can belong to different players
over time.

### A match's teams can be ids or names

'matches.home_team_id' and 'away_team_id' are nullable, with
'home_team_name' / 'away_team_name' as the alternative.

Opponents are frequently outside the organization's own team list — a friendly
against a club SPA has no record of. Creating a shadow 'Team' row for every
opponent would pollute the teams domain with records nobody manages, and would
make "list our teams" lie.

The domain and the API schema both enforce "at least one of id or name for each
side", and the error is a 422 with a specific message rather than a database
violation.

### 'is_home' is stored, not inferred

'matches.is_home' records whether the organization's own team played at home.
Every directional metric depends on knowing which side is "us", and inferring it
at query time from team-id comparisons breaks the moment both teams are in the
organization (an intra-squad match).

### Cascades are chosen per relationship

| Relationship                        | On delete   | Why                                                    |
| ----------------------------------- | ----------- | ------------------------------------------------------ |
| organization → teams/players/matches | 'CASCADE'   | The workspace is the owner; deleting it deletes its data |
| organization → memberships          | 'CASCADE'   | A membership without a workspace is meaningless         |
| video → analysis runs               | 'CASCADE'   | Runs are only meaningful in the context of their video  |
| run → datasets/metrics/heatmaps     | 'CASCADE'   | Derived artefacts cannot outlive their provenance       |
| match → videos                      | 'SET NULL'  | Footage outlives a fixture record; do not delete evidence |
| team → match references             | 'SET NULL'  | A historical fixture must survive a team being removed  |
| user → reports.created_by           | 'SET NULL'  | Reports are organizational; a departed analyst's work remains |

The 'SET NULL' choices are the interesting ones. A cascade that deletes a club's
footage because someone tidied up a match record is a data-loss incident, not a
cleanup.

---

## 4. The performance metric model (the most consequential decision)

'''sql
performance_metrics(
  id, organization_id, analysis_run_id,        -- provenance, NOT NULL
  match_id, player_id, team_id,                -- attribution
  scope, category, name, value, unit,
  definition_version, period_label
)

CHECK (
  (scope = 'player' AND player_id IS NOT NULL) OR
  (scope = 'team'   AND team_id   IS NOT NULL) OR
  (scope = 'match')
)
'''

### Why rows and not a JSON blob

The tempting shortcut is a 'metrics JSONB' column on 'analysis_runs'. It is
easier to write, needs no metric catalogue, and is trivially flexible.

It is also the decision that would have to be undone. Coaches will sort by
distance covered, filter by sprint count, trend a player across a season, and
compare two players. In a JSON blob every one of those is a full-table scan and
an application-side sort, and none of them can use an index. The relational
model is not premature normalisation — it is the shape of the questions.

### 'analysis_run_id' is NOT NULL

Every metric is traceable to the run that produced it. Without that link:

* "why did this player's sprint count change?" is unanswerable;
* a pipeline re-run cannot be compared against the previous output;
* a wrong number cannot be investigated.

An untraceable metric is not worth storing.

### 'definition_version' travels with the value

A number is only interpretable together with how it was computed. Sprint
thresholds differ by sport and age group; a model upgrade changes distances
slightly. Storing the definition version means metrics produced under different
definitions are never silently compared.

### Scope is enforced in the database too

The check constraint means a future worker writing directly to the table cannot
create an orphan number. Domain validation protects the application; the
constraint protects the data.

### Indexes are query-shaped

'''sql
ix_metrics_org_category_name  (organization_id, category, name)
ix_metrics_player_name        (player_id, name)
ix_metrics_match              (match_id)
ix_analysis_runs_org_status   (organization_id, status)
ix_videos_org_status          (organization_id, status)
ix_matches_org_played_on      (organization_id, played_on)
'''

Each leads with 'organization_id' where the query is tenant-scoped, because
every read is. '(player_id, name)' serves "this player's distance over time",
which is the single most common analytic query SPA will run.

---

## 5. JSONB policy

JSONB is used in five places, and the test for whether it belongs is one
question:

> **Is the value read and written whole, with no query on its internals?**

If a user might filter or sort by it, it is a column. If it is opaque metadata
that travels with a row, JSONB is correct.

| Column                                  | Why JSONB                                                    |
| --------------------------------------- | ------------------------------------------------------------ |
| 'videos.probe_metadata'                 | Raw 'ffprobe'/ingestion output. Shape is owned by external tooling and changes without notice. |
| 'analysis_runs.pipeline_spec'           | The ML team must be able to add a stage without an API or schema change. |
| 'analysis_runs.stage_results'           | Per-stage diagnostics differ per stage; each reports something different. |
| 'tracking_datasets.provenance'          | Model versions, homography matrix, calibration, thresholds — inherently model-specific. |
| 'heatmap_grids.cells'                   | A dense numeric matrix, always read whole. There is no query like "find cells > 0.8". |
| 'reports.content'                       | A presentation snapshot. Its internal shape changes faster than a relational schema can follow. |

**And what is deliberately *not* JSONB:**

* 'performance_metrics.*' — queried, sorted, trended. Relational (§4).
* 'videos.duration_seconds', 'frame_rate', 'width', 'height', 'codec' — these are
  first-class queryable facts ("show me all 60fps footage"), so they are columns
  rather than buried inside 'probe_metadata'.
* All foreign keys, statuses and dates.

A report's 'content' being JSONB is the one that looks most like a violation, and
it is not: a report is an *immutable snapshot*, never the source of truth for a
metric. Reports read metrics, freeze them, and store the result.

---

## 6. What is deliberately not in the schema

| Not modelled                        | Why                                                                 |
| ----------------------------------- | ------------------------------------------------------------------- |
| Per-frame tracking observations     | ~3.1 million rows per 90-minute match. Storage strategy depends on measured query patterns — see ['video-processing.md'](video-processing.md). |
| Credentials / sessions / tokens     | Authentication mechanism is unresolved. A half-chosen schema would constrain it. |
| A metric catalogue table            | Would need a decision about every metric's definition and unit before any metric exists. |
| Competitions / seasons               | Currently free strings on 'matches' and 'teams'. A season model is a product decision. |
| Per-sport pitch geometry            | Football is the only sport modelled; generalising before implementing a second would be guessing. |
| Soft deletes / an audit log         | Real requirements, but they need a policy (retention, tenancy, legal) that does not exist yet. |
| Events (passes, shots, possessions) | Requires an event-detection model. Out of scope until tracking works. |

---

## 7. Migrations

Alembic, with the database URL read from the environment ('SPA_DATABASE_URL')
rather than 'alembic.ini'. Credentials never live in a committed file.

'''bash
make migrate            # alembic upgrade head
make migration m="add …" # alembic revision --autogenerate -m "…"
make migrate-down       # alembic downgrade -1
'''

### Conventions that matter

* **A fixed naming convention** ('base.py') for constraints and indexes. Without
  it PostgreSQL assigns generated names, and Alembic's autogenerate cannot
  reliably drop or alter them. Fixing it now avoids painful migrations later.
* **'compare_type=True' and 'compare_server_default=True'** in 'env.py'. Subtle
  schema drift otherwise goes unnoticed until it breaks at runtime.
* **'load_models()' is called explicitly** in 'env.py', so a model module that
  was never imported cannot be silently absent from a generated migration.
* **The initial migration is hand-written**, not autogenerated. The baseline is
  the schema every future migration builds on, and its constraints, indexes and
  cascade behaviour are architectural decisions that deserve review — not
  incidental output.
* **Every migration has a real 'downgrade()'.** Being able to reset a development
  database confidently is a prerequisite for working quickly.
* **'ALEMBIC_DATABASE_URL' overrides everything.** That is how CI and the
  integration-test database point migrations elsewhere without touching
  application settings.

### Running migrations

Migrations run with a **synchronous** psycopg connection derived from the same
URL the application uses, so there is one source of truth for the database
location. The application itself uses the async driver.

---

## 8. Identifier and timestamp conventions

**UUIDs ('uuid.Uuid') rather than 'bigserial'.**

* Identifiers are generated by the application, so a future independent worker
  can create analysis results without a round-trip to the database.
* Sequential ids leak business information — a competitor can infer how many
  matches an organization has processed from an id.
* The domain 'NewType's ('OrganizationId', 'MatchId', …) make a team id where a
  match id is expected a type error, not a production bug.

**All timestamps are 'TIMESTAMP WITH TIME ZONE', defaulted by the database
('now()'), and written as UTC.** Analysis results from different workers must be
comparable without guessing a timezone.

**Statuses are 'varchar' with domain-side validation, not PostgreSQL enum
types.** Adding a state ('archived', 'quarantined') should not require a
migration that rewrites a type and its dependents.

---

## 9. Tenancy enforcement

Tenancy is enforced at three levels, deliberately redundantly:

1. **Storage:** object-storage keys are namespaced '<organization_id>/…', so a
   path bug cannot produce a cross-tenant object read.
2. **Query:** every organization-scoped repository method filters on
   'organization_id', in the repository rather than the route handler.
3. **Response:** a cross-tenant read returns **404, not 403** — returning 403
   would confirm that another tenant's id exists.

What is *not* yet enforced: row-level security in PostgreSQL. That is a
defensible next step once authentication lands and the role model is settled,
because RLS policies need to know who the caller is. See
['overview.md'](overview.md) §8.

---

## 10. Inspecting the database

'''bash
make db-shell                                            # psql session
docker compose exec postgres psql -U spa -d spa -c '\dt'  # list tables
'''

Useful checks:

'''sql
-- Nothing has escaped its organization
SELECT count(*) FROM videos v
LEFT JOIN organizations o ON o.id = v.organization_id
WHERE o.id IS NULL;                             -- expect 0

-- Every metric is traceable
SELECT count(*) FROM performance_metrics WHERE analysis_run_id IS NULL;  -- expect 0
'''