"""Job dispatcher and queue adapters.

'QueuedJobDispatcher' writes the durable job row and enqueues its identifier.
'KeyDbJobQueue' is the production queue; 'InMemoryJobQueue' preserves the same
at-least-once semantics for tests. 'RecordingJobQueue' is the inline development
backend, which writes the row but delivers nothing because no worker runs.
"""

from app.infrastructure.jobs.dispatcher import QueuedJobDispatcher, RecordingJobQueue
from app.infrastructure.jobs.keydb_queue import KeyDbJobQueue
from app.infrastructure.jobs.queue import InMemoryJobQueue

__all__ = [
    "InMemoryJobQueue",
    "KeyDbJobQueue",
    "QueuedJobDispatcher",
    "RecordingJobQueue",
]
