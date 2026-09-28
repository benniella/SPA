# ML tests

Phase 5 implemented the CV pipeline, so this suite is real. It is designed to
run on CPU with no network access and no model weights.

| File               | Covers                                                          |
| ------------------ | --------------------------------------------------------------- |
| 'test_video.py'    | metadata, frame iteration, sampling, corrupt input, streaming    |
| 'test_detection.py'| detection schema, registry, the HOG detector, confidence filtering |
| 'test_tracking.py' | tracker contract, stable ids, multiple objects, missed detections |
| 'test_pipeline.py' | detector → tracker integration, progress, empty results, failure  |

## Fixtures

No video files are committed. 'conftest.py' writes a tiny synthetic clip at test
time with OpenCV, and the detection, tracking and pipeline tests use a scripted
detector and tracker so nothing depends on model output.

## Priority order for future tests

1. **'analysis/' first.** It is pure computation over trajectories:
deterministic, cheap, and testable with synthetic data. Distance and speed from
a known straight-line trajectory are exactly assertable, and getting this wrong
silently corrupts every number a coach sees.
2. **Calibration second.** A pixel→pitch homography that is off by a few percent
scales every distance metric by the same error, and nothing will look broken.
3. **Detection and tracking last, and never with a hard pass/fail on real
footage.** Model output varies between runs and across hardware. Assert
properties (recall above a floor, id switches below a ceiling) on a small,
versioned fixture set instead of exact values.
