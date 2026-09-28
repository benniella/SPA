"""Typed identifiers for the performance-metrics domain."""

from __future__ import annotations

import uuid
from typing import NewType

PerformanceMetricId = NewType("PerformanceMetricId", uuid.UUID)
HeatmapGridId = NewType("HeatmapGridId", uuid.UUID)
