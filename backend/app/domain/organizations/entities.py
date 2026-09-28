"""Organizations: the tenancy and data-ownership boundary of SPA.

Every team, player, match, video and analysis run belongs to exactly one
organization. This is the boundary that makes the platform multi-tenant and
that scopes every storage path, job payload and query.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.shared import OrganizationId, Slug, new_id, utcnow


@dataclass(slots=True)
class Organization:
    """A club, academy, federation or analysis workspace.

    The organization — not the user — owns performance data. Users gain access
    through membership, which is why everything downstream carries an
    ' 'organization_id' '.
    """

    name: str
    slug: Slug
    id: OrganizationId = field(default_factory=lambda: OrganizationId(new_id()))
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Organization name must not be empty.")

    def rename(self, name: str) -> None:
        if not name.strip():
            raise ValueError("Organization name must not be empty.")
        self.name = name
        self.updated_at = utcnow()


@dataclass(slots=True)
class OrganizationMembership:
    """A user's participation in an organization.

    Carries the role, so authorization never has to be inferred from the user
    record. Kept in the organizations domain because the role vocabulary is a
    property of the tenancy model, not of the user profile.
    """

    organization_id: OrganizationId
    user_id: object  # UserId — left untyped to avoid a domain-to-domain import cycle
    role: MembershipRole
    id: object = field(default=None)
    created_at: datetime = field(default_factory=utcnow)


# Role vocabulary. Deliberately a small, explicit set rather than a permission
# matrix: the permission model is a later decision (see architecture risks).
Roles = ("owner", "admin", "coach", "analyst", "viewer")


class MembershipRole:
    """The role a user holds inside an organization.

    Implemented as a constrained string rather than an Enum so that additional
    roles can be introduced without a database enum migration.

    Class-level constants mirror the module-level ' 'Roles' ' tuple so callers can
    write ' 'MembershipRole.OWNER' ' instead of a bare string literal.
    """

    __slots__ = ("value",)

    OWNER = "owner"
    ADMIN = "admin"
    COACH = "coach"
    ANALYST = "analyst"
    VIEWER = "viewer"

    ALLOWED = frozenset(Roles)

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown membership role: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"MembershipRole({self.value!r})"

    def __eq__(self, other: object) -> bool:
        # Comparable with both the constrained type and the raw string, so
        # 'role == MembershipRole.OWNER' and 'role == "owner"' agree. Every
        # constrained-string type in the domain behaves this way.
        if isinstance(other, MembershipRole):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)

    @property
    def can_manage_organization(self) -> bool:
        return self.value in {"owner", "admin"}

    @property
    def can_manage_analysis(self) -> bool:
        return self.value in {"owner", "admin", "coach", "analyst"}
