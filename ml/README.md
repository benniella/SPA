# SPA — ML / Computer Vision

**This directory holds the computer-vision implementation. Phase 5 implemented
the first real pipeline: frame extraction → detection → tracking.**

It exists so that computer-vision work has a home that is structurally separated
from the FastAPI application.

---

## The separation rule

'''
backend/  ──►  serves HTTP, owns PostgreSQL, dispatches jobs
ml/       ──►  reads video, produces data, writes results
'''

'backend/' must never import from 'ml/'. The dependency is one-directional and
enforced by the fact that they are separate Python distributions: the API
declares no dependency on this package, and the worker declares a dependency on
the API's 'app.domain' and 'app.infrastructure' packages for persistence.

This is the rule that keeps SPA a product platform with an ML subsystem, rather
than a research codebase with an API bolted on.

---

## Layout

'''
ml/
├── detection/     object/player detection
├── tracking/      identity association across frames
├── video/         frame decoding and sampling
├── pipelines/     wires decoder → detector → tracker
├── analysis/      movement, heatmaps, team shape, metrics
├── models/        model artefacts (git-ignored — never commit weights)
├── notebooks/     exploratory work, not production
├── experiments/   experiment configs and run outputs (git-ignored)
├── tests/         CV unit tests (synthetic fixtures, fake detector/tracker)
└── pyproject.toml dependency boundary
'''

| Directory      | Will contain                                                                 |
| -------------- | ---------------------------------------------------------------------------- |
| 'detection/'   | Person detection. A ' 'Detector' ' protocol, a registry, and the built-in ' 'HogPersonDetector' '. |
| 'tracking/'    | Assigns **stable 'track_id's** across frames. A ' 'Tracker' ' protocol, a registry, and ' 'CentroidTracker' '. |
| 'video/'       | ' 'OpenCvVideoDecoder' ' (sequential, never loads a whole video) and ' 'FixedIntervalSampler' '. |
| 'pipelines/'   | ' 'CvPipeline' ': runs decoder → detector → tracker, handing tracks to a sink. |
| 'analysis/'    | Turns trajectories into meaning: distance, speed, sprint zones, heatmaps, team shape, intensity breakdown. Pure computation over tracking data — no models. |
| 'models/'      | Model artefacts and metadata. Git-ignored; fetched by a dedicated step, never downloaded implicitly at runtime. |
| 'notebooks/'   | Exploration. Explicitly *not* a deployment path.                             |
| 'experiments/' | Config-driven runs with recorded parameters and metrics, so results are comparable. |

---

## What Phase 5 implemented

```
video file
   ↓  OpenCvVideoDecoder + FixedIntervalSampler
sampled frames
   ↓  Detector (hog_person by default)
per-frame detections
   ↓  Tracker (centroid by default)
stable tracks
   ↓  callback
backend persistence (tracking_observations)
```

The detector and tracker are resolved from a **registry by name**, never a
filesystem path, so a misconfigured value cannot make the worker run arbitrary
code. Both are interfaces, so either can be replaced without touching the
pipeline, the worker or the backend.

### Detector: 'hog_person'

OpenCV's built-in HOG + linear SVM person detector. It ships with OpenCV, needs
no weights file and no GPU, so CPU development and the test suite work with no
setup. It is a classical detector and less accurate than a modern network on
wide-angle footage — which is the reason the interface exists.

### Tracker: 'centroid'

Greedy nearest-centre association with a per-track miss budget. Simple and
deterministic: a moving object keeps its id, and a briefly missed detection does
not spawn a new one. It has no motion or appearance model, so it does not survive
long occlusions or crossings. A Kalman- or IoU-based tracker replaces it behind
the same interface.

### Configuration

The worker passes 'SPA_CV_*' ' settings (detector name, confidence threshold,
device, frame interval, batch size) to the pipeline. Model weights are never
downloaded at startup, and API startup does not depend on a model being present.

---

## What is still not implemented

The hardest decisions in this subsystem are not architectural, they are
empirical:

* **Calibration.** How pixel space maps to pitch space is undecided, so
tracking observations are persisted in **source-frame pixels** with no
'pitch_x'/'pitch_y' columns. See 'docs/architecture/video-processing.md' §9.
* **Model choice for sports footage.** 'hog_person' is a starting point, not a
conclusion. A detector trained on broadcast or wide-angle footage is a future
phase.
* **Identity, teams, jersey numbers, poses, segmentation.** All later phases.
A detected person is a detected object, never a 'player'.

See 'docs/architecture/video-processing.md' for the full analysis.

---

## The contract this directory must honour

Whatever is implemented here, the boundary is fixed:

1. **Input**: a video in object storage plus an 'analysis_run_id'.
2. **Output**: rows written through the backend's repositories — a
   'tracking_dataset', 'performance_metrics', and 'heatmap_grids'.
3. **Provenance**: every artefact records the model versions and parameters that
   produced it, in the 'provenance' JSONB column.
4. **Immutability**: re-running creates a new dataset; existing rows are never
   mutated in place.
5. **Failure**: a failed stage marks the 'analysis_run' failed or partially
   succeeded with a message. It never crashes the API process, because it never
   runs inside it.

---

## Setup

Dependencies are deliberately minimal. The CV stack is an optional extra:

'''bash
cd ml
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,cv]"
'''

OpenCV is pinned below 5.x because OpenCV 5 removed the HOG descriptor API the
built-in person detector uses. The 'worker' extra is unused by the Phase 5
worker, which runs from the backend's own dependency set.

## Running the tests

The CV tests need no GPU, no model weights and no network: the decoder tests use
a tiny synthetic clip written at test time, and the detection/tracking/pipeline
tests use a scripted detector and tracker.

'''bash
cd ..
backend/.venv/bin/python -m pytest ml/tests -q
'''