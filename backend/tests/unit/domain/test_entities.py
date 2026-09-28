"""Domain invariant tests.

These are the tests that justify keeping the domain free of frameworks: they run
in milliseconds, need no database and no HTTP server, and they pin down the
behaviour the rest of the system depends on.
"""

from __future__ import annotations

import pytest

from app.domain.matches.entities import Match, MatchVenue
from app.domain.organizations.entities import MembershipRole, Organization
from app.domain.players.entities import Player, TeamMembership
from app.domain.shared import OrganizationId, PlayerId, Slug, TeamId, new_id
from app.domain.teams.entities import Team
from app.domain.users.entities import Email, User
from app.domain.videos.entities import Video, VideoStatus


class TestOrganization:
    def test_requires_a_name(self) -> None:
        with pytest.raises(ValueError):
            Organization(name="  ", slug=Slug("acme"))

    def test_rename_updates_timestamp(self) -> None:
        organization = Organization(name="Acme", slug=Slug("acme"))
        before = organization.updated_at
        organization.rename("Acme FC")
        assert organization.name == "Acme FC"
        assert organization.updated_at >= before


class TestMembershipRole:
    @pytest.mark.parametrize("role", ["owner", "admin", "coach", "analyst", "viewer"])
    def test_accepts_known_roles(self, role: str) -> None:
        assert str(MembershipRole(role)) == role

    def test_rejects_unknown_role(self) -> None:
        with pytest.raises(ValueError):
            MembershipRole("superuser")

    def test_permissions_follow_the_role(self) -> None:
        assert MembershipRole("owner").can_manage_organization
        assert not MembershipRole("viewer").can_manage_organization
        assert MembershipRole("analyst").can_manage_analysis


class TestEmail:
    def test_normalises_case(self) -> None:
        assert Email("  Coach@Example.COM ").value == "coach@example.com"

    @pytest.mark.parametrize("invalid", ["nope", "nope@", "@example.com", "a@b@c.com"])
    def test_rejects_invalid_addresses(self, invalid: str) -> None:
        with pytest.raises(ValueError):
            Email(invalid)


class TestUser:
    def test_deactivate_keeps_history(self) -> None:
        user = User(email=Email("coach@example.com"), display_name="Coach")
        user.deactivate()
        assert user.is_active is False


class TestTeam:
    def test_defaults_to_football(self) -> None:
        team = Team(
            organization_id=OrganizationId(new_id()),
            name="First Team",
            slug=Slug("first-team"),
        )
        assert team.sport == "football"


class TestPlayerAge:
    def test_age_is_none_without_a_date_of_birth(self) -> None:
        player = Player(organization_id=OrganizationId(new_id()), display_name="A")
        assert player.age_years is None

    def test_age_is_computed_from_date_of_birth(self) -> None:
        from datetime import date

        player = Player(
            organization_id=OrganizationId(new_id()),
            display_name="A",
            date_of_birth=date(2000, 1, 1),
        )
        assert player.age_years is not None and player.age_years >= 24


class TestTeamMembership:
    def test_covers_an_active_registration(self) -> None:
        from datetime import date

        membership = TeamMembership(
            team_id=TeamId(new_id()),
            player_id=PlayerId(new_id()),
            joined_on=date(2024, 7, 1),
        )
        assert membership.is_active
        assert membership.covers(date(2025, 3, 1))

    def test_does_not_cover_before_joining(self) -> None:
        from datetime import date

        membership = TeamMembership(
            team_id=TeamId(new_id()),
            player_id=PlayerId(new_id()),
            joined_on=date(2024, 7, 1),
        )
        assert not membership.covers(date(2024, 6, 30))

    def test_transfer_window_is_closed(self) -> None:
        from datetime import date

        membership = TeamMembership(
            team_id=TeamId(new_id()),
            player_id=PlayerId(new_id()),
            joined_on=date(2023, 1, 1),
            left_on=date(2024, 1, 1),
        )
        # The point of the dated registration: a match played after the transfer
        # must not resolve this player into the old squad.
        assert membership.covers(date(2023, 12, 31))
        assert not membership.covers(date(2024, 1, 2))
        assert not membership.is_active

    def test_rejects_inverted_window(self) -> None:
        from datetime import date

        with pytest.raises(ValueError):
            TeamMembership(
                team_id=TeamId(new_id()),
                player_id=PlayerId(new_id()),
                joined_on=date(2024, 1, 1),
                left_on=date(2023, 1, 1),
            )

    def test_rejects_impossible_shirt_number(self) -> None:
        from datetime import date

        with pytest.raises(ValueError):
            TeamMembership(
                team_id=TeamId(new_id()),
                player_id=PlayerId(new_id()),
                joined_on=date(2024, 1, 1),
                shirt_number=100,
            )


class TestMatch:
    def test_requires_both_sides(self) -> None:
        from datetime import date

        with pytest.raises(ValueError):
            Match(organization_id=OrganizationId(new_id()), played_on=date(2025, 1, 1))

    def test_accepts_named_opponents(self) -> None:
        from datetime import date

        match = Match(
            organization_id=OrganizationId(new_id()),
            played_on=date(2025, 1, 1),
            home_team_name="Us",
            away_team_name="Them",
            venue=MatchVenue(is_home=False),
        )
        assert match.label == "Us vs Them"
        assert match.venue.is_home is False


class TestVideoLifecycle:
    def _video(self) -> Video:
        return Video(
            organization_id=OrganizationId(new_id()),
            original_filename="match.mp4",
            storage_key="org/videos/match.mp4",
        )

    def test_starts_awaiting_upload(self) -> None:
        video = self._video()
        assert video.status == VideoStatus.PENDING
        assert video.is_awaiting_upload
        assert not video.is_analysable

    def test_stored_videos_are_analysable(self) -> None:
        video = self._video()
        video.mark_uploading()
        video.mark_uploaded(size_bytes=4096)
        video.mark_stored()
        assert video.status == VideoStatus.STORED
        assert video.is_analysable

    def test_full_happy_path(self) -> None:
        from app.domain.shared import VideoSpec

        video = self._video()
        video.mark_uploading()
        video.mark_uploaded(size_bytes=4096)
        video.mark_stored(spec=VideoSpec(duration_seconds=5400, frame_rate=25.0))
        video.record_probe(VideoSpec(duration_seconds=5400, frame_rate=25.0), checksum="abc")
        video.mark_processing()
        video.mark_ready()
        assert video.status == VideoStatus.READY
        assert video.checksum == "abc"
        assert video.spec.frame_rate == 25.0

    def test_cannot_mark_uploaded_twice(self) -> None:
        video = self._video()
        video.mark_uploading()
        video.mark_uploaded(size_bytes=4096)
        # The object is already recorded; a second completion must not overwrite it.
        with pytest.raises(ValueError):
            video.mark_uploaded(size_bytes=2048)

    def test_cannot_process_an_unstored_video(self) -> None:
        video = self._video()
        with pytest.raises(ValueError):
            video.mark_processing()

    def test_failure_records_a_reason_and_is_recoverable(self) -> None:
        video = self._video()
        video.mark_uploading()
        video.mark_failed("corrupt container")
        assert video.status == VideoStatus.FAILED
        assert video.failure_reason == "corrupt container"
        # A retried upload must be able to return the video to a usable state.
        video.mark_uploading()
        video.mark_uploaded(size_bytes=4096)
        video.mark_stored()
        assert video.status == VideoStatus.STORED
        assert video.failure_reason is None

    def test_failure_requires_a_reason(self) -> None:
        with pytest.raises(ValueError):
            self._video().mark_failed("  ")  # type: ignore[arg-type]
