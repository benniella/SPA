"""Organization use cases: creating and reading tenancy workspaces."""

from __future__ import annotations

from app.application.ports.unit_of_work import UnitOfWork
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.domain.organizations.entities import MembershipRole, Organization, OrganizationMembership
from app.domain.shared import OrganizationId, Slug, UserId


async def create_organization(
    uow: UnitOfWork,
    *,
    name: str,
    slug: str,
    owner_id: UserId,
) -> Organization:
    """Create a new workspace owned by the caller.

    The slug is validated as a value object here rather than in the route
    handler, so every caller — HTTP today, an admin CLI tomorrow — enforces the
    same rule. The creator is made its owner in the same transaction: a workspace
    nobody belongs to would be unreachable through every scoped endpoint.
    """
    organization = Organization(name=name, slug=Slug(slug))

    async with uow:
        existing = await uow.organizations.get_by_slug(organization.slug.value)
        if existing is not None:
            raise ConflictError(
                "An organization with this slug already exists.",
                details={"slug": organization.slug.value},
            )
        await uow.organizations.add(organization)
        await uow.organizations.add_membership(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=owner_id,
                role=MembershipRole(MembershipRole.OWNER),
            )
        )
        await uow.commit()

    return organization


async def get_organization(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    user_id: UserId,
) -> Organization:
    """Read a workspace the caller belongs to.

    A workspace the caller has no membership in is reported as absent rather than
    forbidden, so the endpoint cannot be used to discover which ids exist.
    """
    await require_organization_member(uow, organization_id=organization_id, user_id=user_id)
    async with uow:
        organization = await uow.organizations.get(organization_id)
        if organization is None:
            raise NotFoundError(f"Organization {organization_id} does not exist.")
        return organization


async def list_organizations(
    uow: UnitOfWork,
    *,
    user_id: UserId,
    limit: int = 50,
    offset: int = 0,
) -> list[Organization]:
    """Every workspace the caller belongs to, and no others."""
    async with uow:
        memberships = await uow.organizations.list_for_user(user_id)
        organizations: list[Organization] = []
        for membership in memberships:
            organization = await uow.organizations.get(membership.organization_id)
            if organization is not None:
                organizations.append(organization)
    organizations.sort(key=lambda item: item.created_at, reverse=True)
    return organizations[offset : offset + limit]


# Roles permitted to mutate an organization's data. 'viewer' is deliberately
# excluded: a read-only member must not be able to upload or delete footage.
WRITE_ROLES = frozenset(
    {MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.COACH, MembershipRole.ANALYST}
)


async def require_organization_member(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    user_id: UserId,
) -> OrganizationMembership:
    """Authorize a user against an organization, or fail.

    Raises:
        NotFoundError: the organization does not exist, or the user is not a
            member. Deliberately the same failure for both: a non-member must not
            be able to probe which organization ids exist.
    """
    async with uow:
        membership = await uow.organizations.get_membership(organization_id, user_id)
    if membership is None:
        raise NotFoundError(f"Organization {organization_id} does not exist.")
    return membership


async def require_organization_writer(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    user_id: UserId,
) -> OrganizationMembership:
    """Authorize a user to create or delete an organization's resources.

    Raises:
        NotFoundError: the organization does not exist or the user is not a member.
        PermissionDeniedError: the user is a member but holds a read-only role.
    """
    membership = await require_organization_member(
        uow, organization_id=organization_id, user_id=user_id
    )
    if membership.role.value not in WRITE_ROLES:
        raise PermissionDeniedError(
            "Your role in this workspace does not allow this action.",
            details={"role": membership.role.value},
        )
    return membership
