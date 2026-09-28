"""The metric catalogue: which metrics exist, in what unit and space.

One place that answers "what does this run's metrics table contain", so the API,
the persistence layer and the frontend read the same list instead of each
maintaining its own.
"""

from __future__ import annotations

from app.domain.metrics.types import MetricName, MetricSpace, MetricUnit

METRIC_CATALOGUE: dict[MetricName, tuple[MetricUnit, MetricSpace]] = {
    MetricName.OBSERVATION_COUNT: (MetricUnit.COUNT, MetricSpace.SOURCE),
    MetricName.DURATION: (MetricUnit.SECONDS, MetricSpace.SOURCE),
    MetricName.COVERAGE: (MetricUnit.COUNT, MetricSpace.SOURCE),
    MetricName.DISPLACEMENT: (MetricUnit.PIXELS, MetricSpace.SOURCE),
    MetricName.AVERAGE_SPEED: (MetricUnit.PIXELS_PER_SECOND, MetricSpace.SOURCE),
    MetricName.PEAK_SPEED: (MetricUnit.PIXELS_PER_SECOND, MetricSpace.SOURCE),
    MetricName.AVERAGE_ACCELERATION: (MetricUnit.PIXELS_PER_SECOND_SQUARED, MetricSpace.SOURCE),
    MetricName.PEAK_ACCELERATION: (MetricUnit.PIXELS_PER_SECOND_SQUARED, MetricSpace.SOURCE),
    MetricName.MEAN_CONFIDENCE: (MetricUnit.COUNT, MetricSpace.SOURCE),
    MetricName.MIN_CONFIDENCE: (MetricUnit.COUNT, MetricSpace.SOURCE),
    MetricName.MAX_CONFIDENCE: (MetricUnit.COUNT, MetricSpace.SOURCE),
}

#: The metric a run's presence is judged by. A run with observations but no
#: counts did not finish its metric stage.
SENTINEL_METRIC = MetricName.OBSERVATION_COUNT
