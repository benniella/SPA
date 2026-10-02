"""Video ingestion use-case tests.

The assertions that matter most: a request must never touch video bytes, a
completion must verify storage rather than trust the client, and no call may
cross an organization boundary.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.application.ports.jobs import Job, JobResult
from app.application.ports.video_storage import StoredObject
from app.application.use_cases.videos import (
    complete_video_upload,
    delete_video,
    request_analysis_run,
    request_video_upload,
)
from app.core.config import Settings
from app.core.errors import (
    ConflictError,
    InvalidStateError,
    NotFoundError,
    PermissionDeniedError,
    UnsupportedMediaError,
    ValidationError,
)
from app.domain.matches.entities import Match
from app.domain.organizations.entities import MembershipRole, OrganizationMembership
from app.domain.shared import MatchId, OrganizationId, UserId, VideoId, new_id
from app.domain.users.entities import Email, User
from app.domain.videos.entities import Video, VideoStatus
from app.infrastructure.storage.keys import build_storage_key
from tests.unit.application.fakes import (
    FakeAnalysisRunRepository,
    FakeVideoRepository,
    UnitOfWorkStub,
)


class FakeVideoStorage:
    """In-memory storage adapter that records calls but transfers no bytes."""

    def __init__(self) -> None:
        self.objects: dict[str, int] = {}
        self.content_types: dict[str, str] = {}
        self.payloads: dict[str, bytes] = {}
        self.presigned: list[str] = []
        self.deleted: list[str] = []

    def build_key(
        self, organization_id: str, *, category: str, owner_id: str, filename: str
    ) -> str:
        # Delegates to the production key builder so the test exercises the real
        # namespacing and filename sanitising rather than a stand-in for them.
        return build_storage_key(
            organization_id, category=category, owner_id=owner_id, filename=filename
        )

    async def presign_upload(
        self,
        key: str,
        *,
        content_type: str | None = None,
        expires_in: int = 3600,
    ) -> str:
        self.presigned.append(key)
        return f"https://storage.test/{key}"

    async def presign_download(self, key: str, *, expires_in: int = 3600) -> str:
        return f"https://storage.test/{key}"

    async def stat(self, key: str) -> StoredObject | None:
        size = self.objects.get(key)
        if size is None:
            return None
        return StoredObject(
            key=key,
            size_bytes=size,
            content_type=self.content_types.get(key),
            last_modified=datetime.now(UTC),
        )

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)
        self.deleted.append(key)

    async def open(self, key: str) -> bytes:
        return self.payloads.get(key, b"")

    async def write_bytes(self, key: str, payload: bytes) -> None:
        self.objects[key] = len(payload)
        self.payloads[key] = payload
        self.content_types.setdefault(key, "application/octet-stream")


class RecordingDispatcher:
    def __init__(self) -> None:
        self.jobs: list[Job] = []

    async def dispatch(self, job: Job) -> JobResult:
        self.jobs.append(job)
        return JobResult(accepted=True, job_id=f"job-{len(self.jobs)}")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://spa:spa@localhost:5432/spa_test",
        session_secret="x" * 32,
    )


@pytest.fixture
def uow() -> UnitOfWorkStub:
    return UnitOfWorkStub()


@pytest.fixture
def storage() -> FakeVideoStorage:
    return FakeVideoStorage()


@pytest.fixture
def dispatcher() -> RecordingDispatcher:
    return RecordingDispatcher()


async def seed_member(
    uow: UnitOfWorkStub,
    organization_id: OrganizationId,
    *,
    role: str = MembershipRole.COACH,
) -> User:
    user = User(email=Email(f"{new_id()}@example.com"), display_name="Coach")
    await uow.users.add(user)
    uow.organizations.memberships.append(
        OrganizationMembership(
            organization_id=organization_id,
            user_id=user.id,
            role=MembershipRole(role),
        )
    )
    return user


async def seed_match(uow: UnitOfWorkStub, organization_id: OrganizationId) -> Match:
    match = Match(
        organization_id=organization_id,
        played_on=date(2026, 1, 1),
        home_team_name="Home",
        away_team_name="Away",
    )
    await uow.matches.add(match)
    return match


class TestRequestVideoUpload:
    async def test_returns_a_presigned_url_without_touching_bytes(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        settings: Settings,
    ) -> None:
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)

        ticket = await request_video_upload(
            uow,
            organization_id=organization_id,
            user_id=user.id,
            filename="match.mp4",
            content_type="video/mp4",
            storage=storage,
            settings=settings,
        )

        assert ticket.upload_url.startswith("https://storage.test/")
        assert storage.presigned == [ticket.storage_key]
        assert uow.videos.added[0].status == VideoStatus.UPLOADING

    async def test_storage_key_is_server_controlled(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        settings: Settings,
    ) -> None:
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)

        ticket = await request_video_upload(
            uow,
            organization_id=organization_id,
            user_id=user.id,
            filename="../../etc/passwd",
            content_type="video/mp4",
            storage=storage,
            settings=settings,
        )

        assert ticket.storage_key.startswith(f"{organization_id}/videos/")
        assert ".." not in ticket.storage_key

    async def test_does_not_dispatch_a_job(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        dispatcher: RecordingDispatcher,
        settings: Settings,
    ) -> None:
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)

        await request_video_upload(
            uow,
            organization_id=organization_id,
            user_id=user.id,
            filename="match.mp4",
            content_type=None,
            storage=storage,
            settings=settings,
        )
        assert dispatcher.jobs == []

    async def test_rejects_an_unsupported_content_type(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        settings: Settings,
    ) -> None:
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)

        with pytest.raises(UnsupportedMediaError):
            await request_video_upload(
                uow,
                organization_id=organization_id,
                user_id=user.id,
                filename="notes.pdf",
                content_type="application/pdf",
                storage=storage,
                settings=settings,
            )
        assert uow.videos.added == []

    async def test_rejects_a_non_member(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        settings: Settings,
    ) -> None:
        organization_id = OrganizationId(new_id())
        outsider = User(email=Email("outsider@example.com"), display_name="Outsider")
        await uow.users.add(outsider)

        with pytest.raises(NotFoundError):
            await request_video_upload(
                uow,
                organization_id=organization_id,
                user_id=outsider.id,
                filename="match.mp4",
                content_type="video/mp4",
                storage=storage,
                settings=settings,
            )

    async def test_rejects_a_read_only_member(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        settings: Settings,
    ) -> None:
        organization_id = OrganizationId(new_id())
        viewer = await seed_member(uow, organization_id, role=MembershipRole.VIEWER)

        with pytest.raises(PermissionDeniedError):
            await request_video_upload(
                uow,
                organization_id=organization_id,
                user_id=viewer.id,
                filename="match.mp4",
                content_type="video/mp4",
                storage=storage,
                settings=settings,
            )

    async def test_rejects_a_match_from_another_organization(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        settings: Settings,
    ) -> None:
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)
        foreign_match = await seed_match(uow, OrganizationId(new_id()))

        with pytest.raises(ValidationError):
            await request_video_upload(
                uow,
                organization_id=organization_id,
                user_id=user.id,
                filename="match.mp4",
                content_type="video/mp4",
                storage=storage,
                settings=settings,
                match_id=foreign_match.id,
            )

    async def test_accepts_a_match_in_the_same_organization(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        settings: Settings,
    ) -> None:
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)
        match = await seed_match(uow, organization_id)

        await request_video_upload(
            uow,
            organization_id=organization_id,
            user_id=user.id,
            filename="match.mp4",
            content_type="video/mp4",
            storage=storage,
            settings=settings,
            match_id=match.id,
        )

        assert uow.videos.added[0].match_id == match.id


class TestCompleteVideoUpload:
    async def _pending_video(
        self,
        uow: UnitOfWorkStub,
        organization_id: OrganizationId,
    ) -> Video:
        video = Video(
            organization_id=organization_id,
            original_filename="match.mp4",
            storage_key=f"{organization_id}/videos/abc/match.mp4",
        )
        video.mark_uploading()
        await uow.videos.add(video)
        return video

    async def test_marks_uploaded_and_dispatches_exactly_one_job(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        dispatcher: RecordingDispatcher,
        settings: Settings,
    ) -> None:
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)
        video = await self._pending_video(uow, organization_id)
        storage.objects[video.storage_key] = 4096
        storage.content_types[video.storage_key] = "video/mp4"

        result = await complete_video_upload(
            uow,
            organization_id=organization_id,
            user_id=user.id,
            video_id=video.id,
            size_bytes=4096,
            checksum=None,
            storage=storage,
            dispatcher=dispatcher,
            settings=settings,
        )

        assert result.status == VideoStatus.UPLOADED
        assert result.size_bytes == 4096
        assert len(dispatcher.jobs) == 1
        assert str(dispatcher.jobs[0].kind) == "ingest_video"
        assert dispatcher.jobs[0].payload == {"video_id": str(video.id)}

    async def test_repeated_completion_is_safe(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        dispatcher: RecordingDispatcher,
        settings: Settings,
    ) -> None:
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)
        video = await self._pending_video(uow, organization_id)
        storage.objects[video.storage_key] = 4096
        storage.content_types[video.storage_key] = "video/mp4"

        first = await complete_video_upload(
            uow,
            organization_id=organization_id,
            user_id=user.id,
            video_id=video.id,
            size_bytes=4096,
            checksum=None,
            storage=storage,
            dispatcher=dispatcher,
            settings=settings,
        )
        second = await complete_video_upload(
            uow,
            organization_id=organization_id,
            user_id=user.id,
            video_id=video.id,
            size_bytes=4096,
            checksum=None,
            storage=storage,
            dispatcher=dispatcher,
            settings=settings,
        )

        assert first.status == VideoStatus.UPLOADED
        assert second.status == VideoStatus.UPLOADED
        # The second call is a no-op: one ingestion job, not two.
        assert len(dispatcher.jobs) == 1

    async def test_rejects_a_missing_object_and_marks_failed(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        dispatcher: RecordingDispatcher,
        settings: Settings,
    ) -> None:
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)
        video = await self._pending_video(uow, organization_id)

        with pytest.raises(InvalidStateError):
            await complete_video_upload(
                uow,
                organization_id=organization_id,
                user_id=user.id,
                video_id=video.id,
                size_bytes=None,
                checksum=None,
                storage=storage,
                dispatcher=dispatcher,
                settings=settings,
            )

        assert dispatcher.jobs == []
        assert uow.videos.added[0].status == VideoStatus.FAILED

    async def test_rejects_a_size_mismatch_and_marks_failed(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        dispatcher: RecordingDispatcher,
        settings: Settings,
    ) -> None:
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)
        video = await self._pending_video(uow, organization_id)
        storage.objects[video.storage_key] = 2048

        with pytest.raises(ConflictError):
            await complete_video_upload(
                uow,
                organization_id=organization_id,
                user_id=user.id,
                video_id=video.id,
                size_bytes=4096,
                checksum=None,
                storage=storage,
                dispatcher=dispatcher,
                settings=settings,
            )

        assert dispatcher.jobs == []
        assert uow.videos.added[0].status == VideoStatus.FAILED

    async def test_rejects_a_stored_object_of_the_wrong_type(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        dispatcher: RecordingDispatcher,
        settings: Settings,
    ) -> None:
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)
        video = await self._pending_video(uow, organization_id)
        storage.objects[video.storage_key] = 4096
        storage.content_types[video.storage_key] = "application/zip"

        with pytest.raises(UnsupportedMediaError):
            await complete_video_upload(
                uow,
                organization_id=organization_id,
                user_id=user.id,
                video_id=video.id,
                size_bytes=4096,
                checksum=None,
                storage=storage,
                dispatcher=dispatcher,
                settings=settings,
            )

        assert uow.videos.added[0].status == VideoStatus.FAILED

    async def test_cannot_complete_another_organizations_upload(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        dispatcher: RecordingDispatcher,
        settings: Settings,
    ) -> None:
        owner_organization = OrganizationId(new_id())
        attacker_organization = OrganizationId(new_id())
        attacker = await seed_member(uow, attacker_organization)
        video = await self._pending_video(uow, owner_organization)
        storage.objects[video.storage_key] = 4096

        with pytest.raises(NotFoundError):
            await complete_video_upload(
                uow,
                organization_id=attacker_organization,
                user_id=attacker.id,
                video_id=video.id,
                size_bytes=4096,
                checksum=None,
                storage=storage,
                dispatcher=dispatcher,
                settings=settings,
            )

        assert dispatcher.jobs == []
        assert video.status == VideoStatus.UPLOADING

    async def test_unknown_video_is_not_found(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
        dispatcher: RecordingDispatcher,
        settings: Settings,
    ) -> None:
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)

        with pytest.raises(NotFoundError):
            await complete_video_upload(
                uow,
                organization_id=organization_id,
                user_id=user.id,
                video_id=VideoId(new_id()),
                size_bytes=None,
                checksum=None,
                storage=storage,
                dispatcher=dispatcher,
                settings=settings,
            )


class TestDeleteVideo:
    async def test_removes_the_record_and_the_object(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
    ) -> None:
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)
        video = Video(
            organization_id=organization_id,
            original_filename="match.mp4",
            storage_key=f"{organization_id}/videos/abc/match.mp4",
        )
        await uow.videos.add(video)
        storage.objects[video.storage_key] = 4096

        await delete_video(
            uow,
            organization_id=organization_id,
            user_id=user.id,
            video_id=video.id,
            storage=storage,
        )

        assert await uow.videos.get(video.id) is None
        assert storage.deleted == [video.storage_key]

    async def test_cannot_delete_another_organizations_video(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
    ) -> None:
        owner_organization = OrganizationId(new_id())
        attacker_organization = OrganizationId(new_id())
        attacker = await seed_member(uow, attacker_organization)
        video = Video(
            organization_id=owner_organization,
            original_filename="match.mp4",
            storage_key=f"{owner_organization}/videos/abc/match.mp4",
        )
        await uow.videos.add(video)

        with pytest.raises(NotFoundError):
            await delete_video(
                uow,
                organization_id=attacker_organization,
                user_id=attacker.id,
                video_id=video.id,
                storage=storage,
            )

        assert storage.deleted == []
        assert await uow.videos.get(video.id) is not None

    async def test_read_only_member_cannot_delete(
        self,
        uow: UnitOfWorkStub,
        storage: FakeVideoStorage,
    ) -> None:
        organization_id = OrganizationId(new_id())
        viewer = await seed_member(uow, organization_id, role=MembershipRole.VIEWER)
        video = Video(
            organization_id=organization_id,
            original_filename="match.mp4",
            storage_key=f"{organization_id}/videos/abc/match.mp4",
        )
        await uow.videos.add(video)

        with pytest.raises(PermissionDeniedError):
            await delete_video(
                uow,
                organization_id=organization_id,
                user_id=viewer.id,
                video_id=video.id,
                storage=storage,
            )

        assert await uow.videos.get(video.id) is not None


class TestRequestAnalysisRun:
    async def _stored_video(self, uow: UnitOfWorkStub) -> Video:
        video = Video(
            organization_id=OrganizationId(new_id()),
            original_filename="match.mp4",
            storage_key="org/videos/match.mp4",
        )
        video.mark_uploaded(size_bytes=4096, content_type="video/mp4")
        video.mark_stored()
        await uow.videos.add(video)
        return video

    async def test_dispatches_a_run_analysis_job(
        self,
        uow: UnitOfWorkStub,
        dispatcher: RecordingDispatcher,
    ) -> None:
        video = await self._stored_video(uow)

        run = await request_analysis_run(
            uow,
            organization_id=video.organization_id,
            video_id=video.id,
            dispatcher=dispatcher,
        )

        assert str(run.status) == "queued"
        assert len(dispatcher.jobs) == 1
        job = dispatcher.jobs[0]
        assert str(job.kind) == "run_analysis"
        assert job.payload["analysis_run_id"] == str(run.id)
        assert job.payload["video_id"] == str(video.id)
        assert "detection" in job.payload["stages"]

    async def test_refuses_an_unstored_video(
        self,
        uow: UnitOfWorkStub,
        dispatcher: RecordingDispatcher,
    ) -> None:
        video = Video(
            organization_id=OrganizationId(new_id()),
            original_filename="match.mp4",
            storage_key="org/videos/match.mp4",
        )
        await uow.videos.add(video)

        with pytest.raises(ConflictError):
            await request_analysis_run(
                uow,
                organization_id=video.organization_id,
                video_id=video.id,
                dispatcher=dispatcher,
            )
        assert dispatcher.jobs == []

    async def test_cross_tenant_access_looks_like_not_found(
        self,
        uow: UnitOfWorkStub,
        dispatcher: RecordingDispatcher,
    ) -> None:
        video = await self._stored_video(uow)

        # A different organization must not be able to confirm that the id
        # exists, so the failure is 404 rather than 403.
        with pytest.raises(NotFoundError):
            await request_analysis_run(
                uow,
                organization_id=OrganizationId(new_id()),
                video_id=video.id,
                dispatcher=dispatcher,
            )
        assert dispatcher.jobs == []

    async def test_persists_the_run_with_its_pipeline(
        self,
        uow: UnitOfWorkStub,
        dispatcher: RecordingDispatcher,
    ) -> None:
        video = await self._stored_video(uow)
        await request_analysis_run(
            uow,
            organization_id=video.organization_id,
            video_id=video.id,
            dispatcher=dispatcher,
        )
        stored = uow.analysis_runs.added[0]
        assert stored.pipeline.stages == (
            "ingest",
            "detection",
            "tracking",
            "movement",
            "metrics",
        )


assert FakeAnalysisRunRepository is not None
assert FakeVideoRepository is not None
assert MatchId is not None
assert UserId is not None
