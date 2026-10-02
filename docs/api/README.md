# API Documentation

The SPA HTTP API is generated from the FastAPI application, so this document
explains how to find and use it rather than duplicating it — a second copy of the
endpoint list would be wrong within a week.

---

## 1. Where the documentation lives

| URL                                       | What it is                                    |
| ----------------------------------------- | --------------------------------------------- |
| 'http://localhost:8000/docs'               | Swagger UI — interactive, try requests here    |
| 'http://localhost:8000/redoc'              | ReDoc — reference layout                       |
| 'http://localhost:8000/openapi.json'       | The OpenAPI 3 document itself                  |

Start the backend with 'make backend-dev' first.

The OpenAPI document is **not** a developer convenience — it is the mechanism
that keeps the frontend's types honest (see §5).

---

## 2. The contract's rules

Four conventions hold across every endpoint. They exist so a frontend developer
learns the API once.

### Versioned prefix

Everything is under '/api/v1'. The version is in the path rather than a header,
so it is visible in logs, in a browser address bar, and in a 'curl' command.

### One error envelope

'''json
{
  "error": {
    "code": "not_found",
    "message": "Video 4e4eb065-… does not exist.",
    "details": { "storage_key": "…" }
  }
}
'''

**Switch on 'code', never on 'message'.** Codes are the contract and are stable;
messages are for humans and will be reworded.

| Code                      | HTTP | When                                              |
| ------------------------- | ---- | ------------------------------------------------- |
| 'validation_error'        | 422  | Payload invalid; 'details.errors' has field detail |
| 'not_found'               | 404  | Missing — **or belonging to another organization** |
| 'conflict'                | 409  | Conflicts with current state (e.g. duplicate slug) |
| 'invalid_state'           | 409  | Wrong lifecycle state for this operation           |
| 'permission_denied'       | 403  | Authenticated, not allowed                         |
| 'authentication_required' | 401  | Not authenticated                                  |
| 'unsupported_media'       | 415  | Upload type or size rejected                       |
| 'infrastructure_error'    | 503  | A dependency failed                                |
| 'internal_error'          | 500  | Unexpected                                         |

'not_found' covering cross-tenant access is deliberate: returning 403 would
confirm that another tenant's identifier exists.

### Pagination is consistent

'''json
{
  "items": [ … ],
  "meta": { "limit": 50, "offset": 0, "count": 12 }
}
'''

'meta' is an object rather than a bare array so a cursor or a total can be added
without breaking clients. Default limit 50, maximum 200.

### Timestamps are ISO-8601 UTC

'2025-09-25T13:40:10.123456Z'. Analysis results from different workers must be
comparable without guessing a timezone.

---

## 3. Endpoints

### Health

| Method | Path                    | Notes                                                  |
| ------ | ----------------------- | ------------------------------------------------------ |
| GET    | '/api/v1/health'         | Liveness. Cheap; does **not** touch the database.      |
| GET    | '/api/v1/health/ready'   | Readiness. Executes 'SELECT 1'; returns 503 if it fails. |

The split matters: a database blip should take a process out of the load
balancer, not cause an orchestrator to restart a healthy API.

### Organizations

| Method | Path                          | Notes                       |
| ------ | ----------------------------- | --------------------------- |
| POST   | '/api/v1/organizations'        | 201; 409 on duplicate slug  |
| GET    | '/api/v1/organizations'        | Paginated                   |
| GET    | '/api/v1/organizations/{id}'   | 404 if absent               |

### Teams · Players · Matches

| Method | Path                 | Notes                                                      |
| ------ | -------------------- | ---------------------------------------------------------- |
| POST   | '/api/v1/teams'       | Requires 'organization_id'                                  |
| GET    | '/api/v1/teams'       | '?organization_id=' required                                |
| POST   | '/api/v1/players'     |                                                             |
| GET    | '/api/v1/players'     | '?organization_id=&team_id=&on_date=' — date-aware squad    |
| POST   | '/api/v1/matches'     | Home/away by id **or** name; 422 if neither                 |
| GET    | '/api/v1/matches'     | '?organization_id=' required                                |

The 'on_date' filter on '/players' resolves the squad as registered on that date,
which is why squad membership is modelled with a validity window rather than a
'team_id' column.

### Videos — the two-step upload

| Method | Path                            | Status | Notes                              |
| ------ | ------------------------------- | ------ | ---------------------------------- |
| POST   | '/api/v1/videos'                 | 201    | Returns a presigned URL            |
| POST   | '/api/v1/videos/{id}/complete'   | 202    | Records it, dispatches ingest      |
| GET    | '/api/v1/videos'                 | 200    | '?organization_id='                 |
| GET    | '/api/v1/videos/{id}'            | 200    |                                     |

**Neither endpoint handles video bytes through the API process:**

'''bash
# 1. Reserve a slot
TICKET=$(curl -s -X POST localhost:8000/api/v1/videos \
  -H 'content-type: application/json' \
  -d '{"organization_id":"'$ORG'","filename":"match.mp4","content_type":"video/mp4"}')

VIDEO_ID=$(echo "$TICKET" | jq -r .video_id)
UPLOAD_URL=$(echo "$TICKET" | jq -r .upload_url)

# 2. Upload directly to storage (S3 in production; the local adapter's own
#    endpoint in development — identical client code)
curl -X PUT "$UPLOAD_URL" -H 'content-type: video/mp4' --data-binary @match.mp4

# 3. Confirm. Returns 202 — probing happens in a worker.
curl -X POST localhost:8000/api/v1/videos/$VIDEO_ID/complete \
  -H 'content-type: application/json' -d '{"size_bytes":123456789}'
'''

Why not a single 'multipart/form-data' upload: routing a 4 GB file through the
API would occupy a worker for minutes and cap upload throughput at the number of
API processes. Presigned URLs make upload a storage problem, not an application
problem.

### Analysis runs — asynchronous by contract

| Method | Path                                 | Status | Notes                            |
| ------ | ------------------------------------ | ------ | -------------------------------- |
| POST   | '/api/v1/analysis-runs'               | **202** | 'Location' header; poll it      |
| GET    | '/api/v1/analysis-runs/{id}'          | 200    | Progress polling                 |
| GET    | '/api/v1/analysis-runs'               | 200    | '?video_id='                      |
| POST   | '/api/v1/analysis-runs/{id}/cancel'   | 200    | Records intent; 409 if finished   |

'''bash
LOCATION=$(curl -s -D - -o /dev/null -X POST localhost:8000/api/v1/analysis-runs \
  -H 'content-type: application/json' \
  -d '{"video_id":"'$VID'","organization_id":"'$ORG'"}' \
  | grep -i '^location:' | tr -d '\r' | awk '{print $2}')

curl -s "localhost:8000$LOCATION?organization_id=$ORG"
'''

'202 Accepted' with a 'Location' header is the whole contract. If this ever
returns '200', the asynchronous architecture has been broken somewhere — which is
why 'tests/unit/api/test_contract.py' asserts the documented status.

There is deliberately **no** 'POST /analysis-runs/{id}/execute'. Work is never
triggered from an HTTP request; the worker owns execution.

### Reports

| Method | Path                                   | Status | Notes                          |
| ------ | -------------------------------------- | ------ | ------------------------------ |
| POST   | '/api/v1/analysis-runs/{id}/reports'     | 202    | Queued generation; 'Location' header |
| GET    | '/api/v1/reports'                        | 200    | '?organization_id='             |
| GET    | '/api/v1/reports/{id}'                   | 200    | Poll for 'status: "ready"'      |

A report is a **snapshot** of one analysis run: its overview, per-track metrics,
deterministic data observations and stated limitations, taken at generation time.
It reads the run's persisted 'tracking_observations' and 'track_metrics' and
computes nothing new. Measurements stay in source-video pixels — no physical unit
is implied.

A report can only be requested once a run has 'succeeded' or
'partially_succeeded'; a run still processing is a '409'. A repeated request for
the same run returns the report already covering it rather than creating a second
snapshot; a failed report is retried in place. Generation runs through the same
job pipeline as video analysis, so 'POST' returns '202' and the report body is
only present once 'status' is '"ready"'.

A downloadable document format is **not** implemented: 'GET /reports/{id}'
returns structured JSON and there is no export control.

### Uploads (local storage only)

| Method | Path                        | Notes                                            |
| ------ | --------------------------- | ------------------------------------------------ |
| PUT    | '/api/v1/uploads/{key}'      | Backs presigned uploads when 'STORAGE_BACKEND=local' |
| GET    | '/api/v1/uploads/{key}'      | Backs presigned downloads                        |

These exist so the presigned-URL contract behaves identically on local disk and
S3. With 'STORAGE_BACKEND=s3', the URLs point at S3 and these endpoints are never
called. They stream in 1 MiB chunks and never buffer a whole video.

---

## 4. Using the API from the frontend

All network I/O goes through 'frontend/src/lib/api-client.ts'. Feature code never
calls 'fetch' directly — that choke point is what makes adding authentication
headers or swapping to a generated client a one-file change.

'''typescript
import { api, ApiError } from "@/lib/api-client";
import type { AnalysisRun } from "@/types/api";

try {
  const run = await api.post<AnalysisRun>("/analysis-runs", {
    video_id: videoId,
    organization_id: organizationId,
  });
} catch (error) {
  if (error instanceof ApiError && error.code === "conflict") {
    // The video is not in an analysable state yet.
  }
}
'''

---

## 5. Generating a typed client

**This is the Phase 1 task that removes the biggest contract risk in the
frontend.**

Today 'frontend/src/types/api.ts' mirrors the Pydantic schemas *by hand*. It is
deliberately minimal — only the shapes the Phase 0 shell touches — because
hand-maintaining a full duplicate guarantees drift.

The intended flow:

'''
FastAPI schemas  →  /openapi.json  →  generated TypeScript  →  types/generated/
'''

Recommended tooling: 'openapi-typescript' (types only, no runtime, no opinion
about how you fetch) or 'openapi-fetch' (types plus a thin typed client that
would replace 'lib/api-client.ts').

A 'package.json' script should generate into a **git-tracked** directory, so a
backend contract change appears in review as a diff of the frontend's types.
That is the property that makes the contract single-sourced rather than merely
generated.

Also worth generating in Phase 1: an assertion in the backend test suite that
'/openapi.json' is valid and that the analysis-run endpoint still documents
'202'. A broken contract should fail CI, not be discovered by the frontend.

---

## 6. Not yet in the API

| Missing                              | Blocked by                                  |
| ------------------------------------ | ------------------------------------------- |
| Authentication (login, tokens)        | Mechanism not chosen                        |
| Authorization enforcement             | Role model not settled                      |
| Tracking data endpoints               | Storage strategy not decided                |
| Heatmap retrieval                      | Depends on tracking output                  |
| Metric query and aggregation endpoints | Need real metrics to design against         |
| Report export (PDF or other document)  | Not implemented; reports are served as JSON  |
| Video thumbnail URL                    | Depends on worker ingest                    |
| Bulk / batch operations                | No measured need yet                        |