"""Storage key construction, shared by every storage adapter.

Keys are namespaced by organization first, so a query or migration bug cannot
become a cross-tenant object read, and by category second, so lifecycle rules
can be applied per prefix.
"""

from __future__ import annotations

import re
import uuid
from pathlib import PurePosixPath

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
# Preserve the extension but cap the stem: some clients send 300-character names.
_MAX_STEM = 80


def sanitise_filename(filename: str) -> str:
    """Reduce an arbitrary uploaded filename to a safe, stable object name."""
    # Take the basename defensively: clients have been known to send paths.
    name = PurePosixPath(filename.replace("\\", "/")).name or "upload"
    stem, dot, suffix = name.rpartition(".")
    if not dot:
        stem, suffix = name, ""
    stem = _UNSAFE.sub("_", stem)[:_MAX_STEM] or "upload"
    suffix = _UNSAFE.sub("", suffix)[:16]
    return f"{stem}.{suffix}" if suffix else stem


def build_storage_key(
    organization_id: str,
    *,
    category: str,
    owner_id: str,
    filename: str,
) -> str:
    """Build a unique, namespaced storage key.

    Format: ' '<organization_id>/<category>/<owner_id>/<uuid>-<safe-filename>' '.

    Organization first, so a query or tenancy bug cannot become a cross-tenant
    object read, and the owning record's id second, so every object belonging to
    one video sits under one prefix that can be deleted wholesale. The original
    filename is never the object's identity: a UUID prefix keeps a re-upload of
    "Match 1.mp4" from overwriting the earlier one.
    """
    safe_category = _UNSAFE.sub("_", category)
    safe_owner = _UNSAFE.sub("_", owner_id)
    return str(
        PurePosixPath(
            str(organization_id),
            safe_category,
            safe_owner,
            f"{uuid.uuid4().hex[:12]}-{sanitise_filename(filename)}",
        )
    )
