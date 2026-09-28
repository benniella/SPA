# Video-Processing Architecture

How SPA turns a match recording into performance data, and why it is built the
way it is.

The central constraint, stated once and then explained:

> **No HTTP request ever performs video processing.**

---

## 1. Why this constraint exists

A 90-minute match at 25 fps is 135,000 frames. Detection, tracking, calibration
and metric extraction on that is minutes to hours of compute, depending on
hardware. Some of it may need a GPU.

The failure modes if that ran inside a request:

| Failure                          | Consequence                                                       |
| -------------------------------- | ----------------------------------------------------------------- |
| HTTP timeout                     | The client gives up; work is already running and cannot be stopped |
| Worker pool exhaustion           | A few concurrent uploads block every other request, including sign-in |
| No retry                         | A transient failure loses hours of compute                        |
| No progress                     | The user sees a spinner with no information                       |
| No horizontal scaling            | The API tier and the compute tier must scale together             |
| A crash takes down the platform  | The video pipeline shares a process with the product              |

Every one of those is avoided by one decision: the API records *intent* and
returns immediately; a worker does the work.

---

## 2. The pipeline

'''
                     ┌──────────────────────────────┐
                     │  POST /videos                │
   Next.js ─────────►│  201 + presigned URL         │  no bytes touched
                     └──────────────┬───────────────┘
                                    │
                     ┌──────────────▼───────────────┐
                     │  Object storage              │
                     │  client uploads bytes direct │  API never buffers
                     └──────────────┬───────────────┘
                                    │
                     ┌──────────────▼───────────────┐
                     │  POST /videos/{id}/complete  │
                     │  202 + dispatch(ingest)      │  probe happens in worker
                     └──────────────┬───────────────┘
                                    │
                     ┌──────────────▼───────────────┐
                     │  POST /analysis-runs         │
                     │  202 + Location header       │  creates a run row
                     └──────────────┬───────────────┘
                                    │  JobDispatcher
                    ════════════════╪════════════════   ← the process boundary
                                    │
                    ┌───────────────▼───────────────┐
                    │  ML / video worker            │
                    │  ingest → detection → tracking │
                    │  → movement → metrics          │
                    └───────────────┬───────────────┘
                                    │  writes through repositories
                    ┌───────────────▼───────────────┐
                    │  PostgreSQL                   │
                    │  tracking_datasets            │
                    │  performance_metrics          │
                    │  heatmap_grids                │
                    └───────────────┬───────────────┘
                                    │  poll GET /analysis-runs/{id}
                     ┌──────────────▼───────────────┐
                     │  Dashboard / Reports          │
                     └──────────────────────────────┘
'''

### The stages

| Stage       | Input                       | Output                                  | Where          |
| ----------- | --------------------------- | --------------------------------------- | -------------- |
| 'ingest'    | object-storage key          | duration, frame rate, codec, thumbnails | worker         |
| 'detection' | frames                      | boxes + confidence per object per frame | worker (GPU?)  |
| 'tracking'  | detections                  | **stable 'track_id' per object over time** | worker      |
| 'movement'  | trajectories + calibration  | distance, speed, sprint zones           | worker (CPU)   |
| 'metrics'   | movement output             | 'performance_metrics' rows              | worker (CPU)   |

'tracking' is the pivotal stage. Without stable identities across frames there
are detections, not trajectories — and no distance covered, no sprint count, no
heatmap and no team shape. An identity switch mid-match silently corrupts every
metric derived from it. This is why tracking output is versioned and immutable
(§5).

---

## 3. The seam: 'JobDispatcher'

'''python
# app/application/ports/jobs.py

class JobDispatcher(Protocol):
    async def dispatch(self, job: Job) -> JobResult: ...

@dataclass(frozen=True, slots=True)
class Job:
    kind: JobKind
    payload: dict[str, Any]          # JSON-serialisable, identifiers only
    organization_id: str | None
    idempotency_key: str | None
    max_attempts: int = 3
'''

The API depends on this interface and nothing else.

### Why the payload is a 'dict', not an entity

A job crosses a serialisation boundary. Passing an ORM entity or a domain
dataclass works in-process and fails the moment a real broker is introduced —
and it fails *late*, in a worker, in production. Restricting the payload to
JSON-safe primitives now means serialisability is verified in the current test
suite rather than discovered later.

### What the API does for a long-running task

'''python
run = AnalysisRun(organization_id=..., video_id=..., pipeline=default_pipeline())
run.queue()

await uow.analysis_runs.add(run)
await uow.commit()

await dispatcher.dispatch(
    Job(
        kind=JobKind(JobKind.RUN_ANALYSIS),
        payload={"analysis_run_id": str(run.id), "video_id": str(video_id), "stages": [...]},
        organization_id=str(organization_id),
        idempotency_key=f"analysis:{run.id}",
    )
)
'''

Two rows, one message, no waiting. 'idempotency_key' matters because brokers are
typically at-least-once: a retried dispatch must not start duplicate work.

### Phase 4's implementation

The port is unchanged; the adapter is real. 'SPA_JOB_BACKEND' selects between:

* 'inline' — 'RecordingJobQueue' writes the durable job row and records the
  enqueue without delivering it. Lets the API run with no KeyDB and no worker.
* 'queued' — 'KeyDbJobQueue' enqueues the job identifier for a worker process
  ('python -m app.worker.main').

Both write the same 'processing_jobs' row first, so the row — not the queue
message — is the source of truth. The queue is a reliable one: 'BRPOPLPUSH'
moves an identifier into a processing list, and it is removed only on
acknowledgement, so a worker that crashes after claiming a job does not lose it.

See §6 for how progress now reaches the client.

---

## 4. Migrating to a real worker

| Change                                        | Type           |
| --------------------------------------------- | -------------- |
| Add 'app/infrastructure/jobs/celery.py'        | New adapter    |
| Set 'SPA_JOB_BACKEND=celery'                   | Configuration  |
| Add 'worker' and 'redis' services to compose   | Infrastructure |
| **Use cases, domain, routers, schema**         | **Unchanged**  |

The Celery adapter implements the same port:

'''python
class CeleryJobDispatcher:
    def __init__(self, broker_url: str) -> None:
        self._app = Celery(broker=broker_url)

    async def dispatch(self, job: Job) -> JobResult:
        # The payload is already JSON-safe by construction, so this is a direct
        # hand-off rather than a translation.
        self._app.send_task(
            f"spa.{job.kind}",
            kwargs=job.payload,
            task_id=job.idempotency_key,
        )
        return JobResult(accepted=True, job_id=job.idempotency_key)
'''

That is the whole change. It is possible because:

* the domain has no framework dependency, so the worker imports it directly;
* use cases depend on ports, so the worker calls the same 'request_analysis_run';
* payloads are already serialisable;
* 'organization_id' travels with the job, so the worker does not have to look up
  tenancy context (which would be a query it might get wrong).

### Recommended broker and why

**Celery + Redis** when the worker is extracted, for one reason: Python-native
task routing and retry semantics, and Redis is already a familiar operational
dependency. The alternative — a cloud queue (SQS, Cloud Tasks) — is a better fit
once deployment is decided, and is a new adapter, not a rewrite. The choice is
deferred until there is a deployment target to choose for.

**Rejected: Kafka.** SPA dispatches hundreds of jobs per match collection, not
millions of events per second. A log-based broker would add operational weight
(partitions, consumer groups, offset management) for no benefit at this scale.
**Rejected: event sourcing / CQRS.** Same reasoning, applied to state: SPA's
state transitions are few, well-understood and best read directly from the row.

---

## 5. Versioning, provenance and immutability

Three rules that make analysis results trustworthy.

### Re-running creates a new dataset

'TrackingDataset' rows are never mutated in place. Re-running tracking with a
better model produces a *new* dataset, and metrics keep a pointer to the run and
dataset they came from.

Without this, re-running the pipeline silently changes historical numbers and a
season review becomes unreproducible.

### Every metric records how it was computed

'PerformanceMetric.definition_version' and 'TrackingDataset.provenance' capture
model versions, thresholds, and calibration. Sprint thresholds differ by sport
and age group; a model upgrade shifts distances slightly. Without the version,
numbers computed under different definitions get compared as though equivalent.

'TrackingDataset.provenance' also holds the homography matrix. Coordinates are
**normalised pitch metres**, not image pixels — pixels are meaningless without
the calibration, which differs per video. Metres are directly comparable across
matches.

### Partial success is a distinct outcome

'AnalysisRunStatus.PARTIALLY_SUCCEEDED' exists because a multi-stage pipeline can
produce usable tracking data while a later stage fails. Collapsing that into
'failed' would discard hours of valid, expensive work.

---

## 6. Progress reporting

Two paths, and the database is authoritative for both:

* **Live events.** An authenticated WebSocket at '/ws/processing' delivers
  'processing.queued|started|progress|completed|failed' for one organization.
  Authorization is resolved server-side at connect time from the user's
  membership, so a connection for Organization A cannot receive Organization B's
  events. Events are notifications only; they never carry a storage key, a signed
  URL or a stack trace.
* **Polling.** 'GET /videos/{id}/processing' returns the video's status and its
  latest job. This is the fallback a client reads after a reconnect, which is why
  a missed event is a latency problem and never a correctness one.

Across processes, the worker publishes events to KeyDB and each API process
bridges them into its own connections; the same organization-scoped delivery
path is used either way.

The 'processing_jobs' row carries 'status', 'progress', 'attempt',
'max_attempts', 'error', 'started_at' and 'completed_at'. A failure is retried
while the job's own 'max_attempts' budget allows and then left 'failed', with the
video marked 'failed' and a persisted reason.

'stage_results' (JSONB) on an analysis run accumulates per-stage diagnostics, so
a partially completed run can report *which* stage failed without loading
trajectories.

---

## 7. The unresolved storage question

**This is the biggest open decision in the platform.** It is not resolved because
the information needed does not exist yet.

A 90-minute match at 25 fps with 23 tracked objects is roughly **3.1 million
observations**. Two defensible strategies:

### Option A — columnar file in object storage

'''
tracking_datasets/{id}/observations.parquet
'''

* Cheap and fast to write sequentially.
* Compresses very well (trajectories are highly regular).
* Fast to load whole for bulk analysis.
* Cannot be queried or filtered without loading.
* 'TrackingDataset.storage_key' already exists for this.

### Option B — PostgreSQL table with time partitioning

'''sql
tracking_observations(
  dataset_id, frame_index, track_id, object_type,
  confidence, pitch_x, pitch_y, bbox...
) PARTITION BY RANGE (frame_index)
'''

* Queryable: "all frames where player 7 was in the final third".
* Supports frame-by-frame scrubbing without a file fetch.
* Expensive: 3.1M rows per match, and SPA is designed for many matches.
* Vacuum, index bloat and backup size all become real concerns.

### What would resolve it

Measured query patterns:

* If coaches scrub tracking frame by frame → Option B (or B for recent matches,
  A for archive).
* If they only look at derived heatmaps and metrics → Option A wins by a wide
  margin, because the observations are never queried directly.
* A hybrid is likely: recent matches queryable, older ones columnar.

Because 'TrackingDataset' stores 'storage_key' and counters, adopting either is a
storage-layer change rather than a schema change. That is the entire reason the
decision can be deferred safely.

**What was not done:** guessing, and building a 3-million-row table that has to
be dropped.

---

## 8. Detection persistence

Related and also unresolved: **are raw detections persisted at all?**

Persisting every detection for a match is substantially more data than persisting
the tracks derived from them, and it is only valuable if re-tracking with a
different algorithm is a feature worth building.

The default assumption is **no** — detections are an intermediate result,
consumed by the tracker within one stage execution. If re-tracking becomes a
requirement, 'TrackingDataset.storage_key' generalises to a detections artefact
and the tracker gains a second input mode.

---

## 9. Calibration

Detections are in image pixels. Metrics need pitch metres. The mapping is a
homography derived from pitch landmarks.

| Approach        | Cost                          | Accuracy                        |
| --------------- | ----------------------------- | ------------------------------- |
| Manual          | 30 seconds of coach time      | High, if the coach is careful   |
| Automatic       | Pitch-line detection model    | Variable with camera quality    |
| Fixed camera    | One-time per venue, cached    | Highest, if the camera never moves |

**Why this is not decided:** it is a product and UX decision as much as a
technical one. Manual calibration pushes work onto the coach; automatic
calibration adds a failure mode that is hard to explain. The answer probably
depends on whether SPA's primary footage is a fixed wide-angle club camera (cache
per venue) or varied broadcast footage (per-match, probably automatic).

Until it is decided, 'PitchCoordinate' is documented as normalised metres and
'TrackObservation.pitch_position' is optional so pixel-space detections can still
be persisted.

---

## 10. Failure handling

| Failure                     | Behaviour                                                        |
| --------------------------- | ---------------------------------------------------------------- |
| Upload never completes      | 'Video.status = uploaded'; 'POST /analysis-runs' returns 409      |
| Object missing from storage | 'POST /videos/{id}/complete' returns 409 'invalid_state'          |
| Size mismatch               | 409 'conflict' — catches a truncated upload before it is analysed |
| Ingest probe fails          | 'Video.status = failed' with a reason; retryable by re-uploading  |
| A stage crashes             | 'AnalysisRun.status = failed' with 'error_message'                |
| A later stage fails         | 'partially_succeeded'; earlier results are kept                   |
| Worker dies mid-run         | The run stays 'running' and is reclaimed by a retry or a sweeper  |
| Transient broker failure    | Retried, deduplicated by 'idempotency_key'                        |

The last one identifies work for Phase 1: a stale-'running' reaper. A worker
that dies without cleanup leaves a run looking active forever, and the frontend
would poll indefinitely. Detecting a run whose 'started_at' is far in the past
with no progress, and marking it failed, is necessary rather than optional.

---

## 11. What is explicitly not built in Phase 0

Listed so that "not yet implemented" is not confused with "forgotten".

| Not built                          | Why                                                        |
| ---------------------------------- | ---------------------------------------------------------- |
| Any detector or tracker            | Model choice depends on footage characteristics not measured |
| Calibration                        | Product/UX decision (§9)                                   |
| Metric computation                 | Idle until trajectories exist                              |
| Celery worker, Redis               | No work to execute; would add an unused dependency          |
| S3 adapter                         | No bucket yet; the port is the contract                     |
| Thumbnail extraction               | Belongs with ingest, in the worker                          |
| Stale-run reaper                   | Needs a worker to have stale runs (§10)                     |
| Frame-accurate seeking in the UI   | Needs a player and real footage                             |

Every one of these is reachable through an existing interface. None requires
restructuring. That is the test of whether the Phase 0 boundaries were drawn
correctly.

---

## 12. Phase 5 — the first CV pipeline

Phase 4 established the worker and the durable job lifecycle. Phase 5 replaced
the placeholder pipeline with a real one without changing any of those
boundaries:

'''
video file
   ↓  ml/video/OpenCvVideoDecoder + FixedIntervalSampler
sampled frames (streamed, never accumulated)
   ↓  ml/detection (Detector protocol; hog_person by default)
per-frame detections
   ↓  ml/tracking (Tracker protocol; centroid by default)
stable tracks
   ↓  callback
backend persistence (tracking_observations)
'''

### What changed

| Component              | Change                                                       |
| ---------------------- | ------------------------------------------------------------ |
| 'ProcessingPipeline' port | **Unchanged.** ' 'CvProcessingPipeline' ' implements it. |
| 'JobWorker'            | Unchanged except that it resolves the video's analysis run and passes its id in the context. No detector logic was added. |
| 'ml/'                  | ' 'detection/' ', ' 'tracking/' ', ' 'video/' ', ' 'pipelines/' ' implemented. |
| Database               | One table, ' 'tracking_observations' ', written in bounded batches. |
| Progress               | Reported from frames processed, through the Phase 4 job row. |

### Detector and tracker are registry-resolved

A detector is chosen by a **name** in ' 'SPA_CV_DETECTOR' ' (' 'hog_person' '),
never a path or a client-supplied value. The registry means a misconfigured
deployment fails with "unknown detector" rather than executing arbitrary code in
the worker, and it is the seam through which a trained sports detector is added
later.

### Coordinates are pixels, deliberately

'tracking_observations' has ' 'x1' '/' 'y1' '/' 'x2' '/' 'y2' ' and no pitch
columns, because §9 (calibration) is still undecided. Persisting pixels is
honest: they are what the detector produced. Pitch metres are added by the
calibration phase, which will also backfill via a new dataset rather than
mutating these rows.

### What Phase 5 deliberately did not do

Identity, teams, jersey numbers, re-identification, pose, segmentation, ball
tracking, pitch detection, tactical analysis, event recognition, metrics,
heatmaps and reports are all later phases. A detected person is a detected
object — 'PERSON ≠ PLAYER_ID' — and the schema says so.---

## 13. Phase 6 — the metrics and analysis engine

Phase 5 turned a video into persisted tracking observations. Phase 6 turns those
observations into derived numbers, without changing any of the boundaries above:

'''
tracking_observations
   ↓  repository, one bounded page at a time
per-track observations
   ↓  domain/metrics (pure, deterministic)
track_metrics rows
   ↓  GET /analysis-runs/{id}/metrics
analysis run detail page
'''

### The metrics engine is a domain module, not a service

'app/domain/metrics/' imports nothing but the standard library and the shared
domain primitives. It has no database session, no OpenCV, no detector, no
tracker and no sport vocabulary. That is what lets a future detector or tracker
be replaced without rewriting a single calculation, and what lets a future
calibration layer add a second coordinate space rather than a second engine.

### Everything is source-space until calibration exists

Every metric carries a 'space' ('source') and a 'unit' ('pixels',
'pixels_per_second', …). No metres, no km/h, and no conversion constant: the
calibration that would justify a physical unit does not exist (§9). A metric the
engine could not compute is stored as 'unavailable' with a null value — never as
zero, because "no speed could be measured" and "the speed was zero" are
different statements.

### A tracking gap is not movement

Two consecutive observations more than 'SPA_METRICS_MAX_OBSERVATION_GAP_SECONDS'
apart are not treated as a continuous step. A track that vanishes for a minute
must not read as a player who sprinted across the frame. Duplicate frames,
non-positive time steps and non-increasing frame indices are skipped for the
same reason.

### Metric calculation runs on the Phase 4 job system

'MetricsPipeline' implements the same 'ProcessingPipeline' port as
'CvProcessingPipeline', and the worker selects it by the job's type. There is no
second job system, no second lifecycle and no second progress channel: a metric
calculation is a 'ProcessingJob' like any other, and the 'AnalysisRun' it belongs
to moves through the states it already had.

### Recalculating replaces rather than appends

'track_metrics' is unique on '(analysis_run_id, track_id, metric_name)', and the
repository replaces a run's rows inside one transaction. A retried job therefore
recomputes the same rows instead of duplicating them.

### What Phase 6 deliberately did not do

No new detector or tracker, no calibration, no possession, passes, shots or
tackles, no heatmaps, no performance scores and no reports. The engine produces
the generic quantitative foundation those later phases will read; it does not
guess at sport-specific methodology it cannot yet justify.