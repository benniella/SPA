from fastapi import APIRouter

from app.api.v1 import (
    account,
    admin,
    admin_configuration,
    admin_invitations,
    admin_mfa,
    analysis,
    auth,
    health,
    matches,
    organizations,
    players,
    processing,
    reports,
    teams,
    uploads,
    users,
    videos,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(account.router, prefix="/account", tags=["account"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(players.router, prefix="/players", tags=["players"])
api_router.include_router(matches.router, prefix="/matches", tags=["matches"])
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
# These routers define their complete paths and mount at the API root.
api_router.include_router(processing.router, tags=["processing"])
api_router.include_router(analysis.router, prefix="/analysis-runs", tags=["analysis"])
api_router.include_router(reports.router, tags=["reports"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(
    admin_configuration.router, prefix="/admin", tags=["admin"]
)
api_router.include_router(
    admin_invitations.router, prefix="/admin", tags=["admin"]
)
api_router.include_router(admin_mfa.router, prefix="/admin", tags=["admin"])

__all__ = ["api_router"]
