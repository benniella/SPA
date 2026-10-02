"""The role and privilege catalogue.

One source of truth, imported by both the migration that seeds the tables and the
repository that reads them. Duplicating this list in the migration would let the
seeded rows drift from the privileges the application checks.
"""

from __future__ import annotations

from app.domain.admin.entities import AdminPrivilege as P
from app.domain.admin.entities import AdminRole as R

PRIVILEGE_DESCRIPTIONS: dict[str, str] = {
    P.USERS_READ: "View platform users.",
    P.USERS_MANAGE: "Edit platform user records.",
    P.USERS_SUSPEND: "Suspend a platform user.",
    P.USERS_REACTIVATE: "Reactivate a suspended platform user.",
    P.ORGANIZATIONS_READ: "View organizations.",
    P.ORGANIZATIONS_MANAGE: "Edit organizations.",
    P.BILLING_READ: "View billing and subscription state.",
    P.BILLING_MANAGE: "Change billing and subscription state.",
    P.SUPPORT_READ: "View support requests.",
    P.SUPPORT_MANAGE: "Respond to support requests.",
    P.COMMUNICATIONS_READ: "View communications and campaigns.",
    P.COMMUNICATIONS_SEND: "Send communications to users.",
    P.SYSTEM_READ: "View system status and metrics.",
    P.SYSTEM_MANAGE: "Change system settings.",
    P.MAINTENANCE_READ: "View maintenance state.",
    P.MAINTENANCE_MANAGE: "Enable and disable maintenance mode.",
    P.SECURITY_READ: "View security events and audit history.",
    P.SECURITY_MANAGE: "Manage security controls.",
    P.JOBS_READ: "View processing jobs.",
    P.JOBS_MANAGE: "Retry and cancel processing jobs.",
    P.REPORTS_READ: "View platform reports.",
    P.CONFIGURATION_READ: "View platform configuration.",
    P.CONFIGURATION_MANAGE: "Change platform configuration.",
    P.ADMINS_READ: "View administrators and their roles.",
    P.ADMINS_MANAGE: "Create, suspend, revoke and re-role administrators.",
}

ROLE_DESCRIPTIONS: dict[str, str] = {
    R.FINANCE_ADMIN: "Billing and subscription administration.",
    R.MAINTENANCE_ADMIN: "Maintenance mode and system settings.",
    R.SUPPORT_ADMIN: "Support request administration.",
    R.ACCOUNT_REVIEW_ADMIN: "Review of user accounts and organizations.",
    R.COMMUNICATIONS_ADMIN: "Outbound communications to users.",
    R.SECURITY_ADMIN: "Security events and security controls.",
    R.OPERATIONS_ADMIN: "Day-to-day platform operations.",
    R.SUPERADMIN: "Full platform authority.",
}

ALL_PRIVILEGES: tuple[str, ...] = tuple(PRIVILEGE_DESCRIPTIONS)

ROLE_PRIVILEGES: dict[str, tuple[str, ...]] = {
    R.FINANCE_ADMIN: (P.BILLING_READ, P.BILLING_MANAGE, P.REPORTS_READ),
    R.MAINTENANCE_ADMIN: (
        P.MAINTENANCE_READ,
        P.MAINTENANCE_MANAGE,
        P.SYSTEM_READ,
        P.JOBS_READ,
    ),
    R.SUPPORT_ADMIN: (
        P.SUPPORT_READ,
        P.SUPPORT_MANAGE,
        P.USERS_READ,
        P.ORGANIZATIONS_READ,
    ),
    R.ACCOUNT_REVIEW_ADMIN: (
        P.USERS_READ,
        P.USERS_SUSPEND,
        P.USERS_REACTIVATE,
        P.ORGANIZATIONS_READ,
    ),
    R.COMMUNICATIONS_ADMIN: (
        P.COMMUNICATIONS_READ,
        P.COMMUNICATIONS_SEND,
        P.USERS_READ,
    ),
    R.SECURITY_ADMIN: (
        P.SECURITY_READ,
        P.SECURITY_MANAGE,
        P.USERS_READ,
        P.USERS_SUSPEND,
        P.REPORTS_READ,
    ),
    R.OPERATIONS_ADMIN: (
        P.SYSTEM_READ,
        P.SYSTEM_MANAGE,
        P.JOBS_READ,
        P.JOBS_MANAGE,
        P.REPORTS_READ,
        P.CONFIGURATION_READ,
    ),
    # Superadmin is expressed as every privilege rather than as a bypass, so a
    # new privilege is granted to it by being added here and cannot be silently
    # missed by an 'is_superadmin' shortcut somewhere in a route.
    R.SUPERADMIN: ALL_PRIVILEGES,
}

__all__ = [
    "ALL_PRIVILEGES",
    "PRIVILEGE_DESCRIPTIONS",
    "ROLE_DESCRIPTIONS",
    "ROLE_PRIVILEGES",
]
