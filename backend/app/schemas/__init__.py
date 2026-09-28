"""Pydantic schemas — the public API contract.

Separate from the SQLAlchemy persistence models: the API contract and the
database schema evolve at different speeds, and sharing a class makes every
column rename a breaking API change. 'Read' models are what the frontend and any
generated TypeScript client consume.
"""

from app.schemas.analysis import (
    AnalysisRunCreate,
    AnalysisRunList,
    AnalysisRunRead,
    PipelineSpecSchema,
)
from app.schemas.common import ErrorBody, ErrorResponse, HealthResponse, PageMeta
from app.schemas.matches import MatchCreate, MatchList, MatchRead
from app.schemas.organizations import (
    OrganizationCreate,
    OrganizationList,
    OrganizationRead,
)
from app.schemas.players import PlayerCreate, PlayerList, PlayerRead
from app.schemas.reports import ReportCreate, ReportList, ReportRead
from app.schemas.teams import TeamCreate, TeamList, TeamRead
from app.schemas.users import UserCreate, UserList, UserRead
from app.schemas.videos import (
    VideoCompleteUpload,
    VideoList,
    VideoRead,
    VideoUploadRequest,
    VideoUploadTicket,
)

__all__ = [
    "AnalysisRunCreate",
    "AnalysisRunList",
    "AnalysisRunRead",
    "ErrorBody",
    "ErrorResponse",
    "HealthResponse",
    "MatchCreate",
    "MatchList",
    "MatchRead",
    "OrganizationCreate",
    "OrganizationList",
    "OrganizationRead",
    "PageMeta",
    "PipelineSpecSchema",
    "PlayerCreate",
    "PlayerList",
    "PlayerRead",
    "ReportCreate",
    "ReportList",
    "ReportRead",
    "TeamCreate",
    "TeamList",
    "TeamRead",
    "UserCreate",
    "UserList",
    "UserRead",
    "VideoCompleteUpload",
    "VideoList",
    "VideoRead",
    "VideoUploadRequest",
    "VideoUploadTicket",
]
