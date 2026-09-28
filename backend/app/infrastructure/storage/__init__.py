"""Storage adapters.

An S3 adapter is intentionally absent: before there is a bucket to talk to it
would be an untested code path and an extra dependency. The port in
'app.application.ports.video_storage' is the contract.
"""

from app.infrastructure.storage.keys import build_storage_key, sanitise_filename
from app.infrastructure.storage.local import LocalVideoStorage

__all__ = ["LocalVideoStorage", "build_storage_key", "sanitise_filename"]
