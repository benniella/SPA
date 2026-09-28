"""Ports (interfaces) the application layer depends on.

Application and domain code define what they need; infrastructure provides it.
Each port is a 'typing.Protocol' rather than an abstract base class, so adapters
need not inherit from anything.
"""

from app.application.ports.jobs import (
    Job,
    JobDispatcher,
    JobKind,
    JobRegistry,
    JobResult,
)
from app.application.ports.repositories import (
    AnalysisRunRepository,
    MatchRepository,
    OrganizationRepository,
    PerformanceMetricRepository,
    PlayerRepository,
    ReportRepository,
    TeamRepository,
    TrackingDatasetRepository,
    TrackMetricRepository,
    UserRepository,
    VideoRepository,
)
from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.application.ports.video_storage import StoredObject, VideoStorage

__all__ = [
    "AnalysisRunRepository",
    "Job",
    "JobDispatcher",
    "JobKind",
    "JobRegistry",
    "JobResult",
    "MatchRepository",
    "OrganizationRepository",
    "PerformanceMetricRepository",
    "PlayerRepository",
    "ReportRepository",
    "StoredObject",
    "TeamRepository",
    "TrackMetricRepository",
    "TrackingDatasetRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
    "UserRepository",
    "VideoRepository",
    "VideoStorage",
]
