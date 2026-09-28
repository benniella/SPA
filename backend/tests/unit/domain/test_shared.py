"""Shared value-object tests."""

from __future__ import annotations

import uuid

import pytest

from app.domain.shared import (
    MetricValue,
    Page,
    Percentage,
    PitchCoordinate,
    Slug,
    TimeRange,
    new_id,
    utcnow,
)


class TestSlug:
    def test_accepts_valid_slug(self) -> None:
        assert Slug("acme-fc").value == "acme-fc"

    @pytest.mark.parametrize(
        "invalid",
        ["Acme", "acme_fc", "-acme", "acme-", "acme--fc", "a", ""],
    )
    def test_rejects_invalid_slug(self, invalid: str) -> None:
        with pytest.raises(ValueError):
            Slug(invalid)


class TestPercentage:
    def test_accepts_bounds(self) -> None:
        assert Percentage(0.0).value == 0.0
        assert Percentage(100.0).value == 100.0

    @pytest.mark.parametrize("invalid", [-0.1, 100.1])
    def test_rejects_out_of_range(self, invalid: float) -> None:
        with pytest.raises(ValueError):
            Percentage(invalid)


class TestMetricValue:
    def test_requires_a_name(self) -> None:
        with pytest.raises(ValueError):
            MetricValue(name="  ", value=1.0)

    def test_carries_definition_version(self) -> None:
        metric = MetricValue(name="distance_covered", value=942.5, unit="m")
        assert metric.definition_version == "v1"


class TestTimeRange:
    def test_computes_duration(self) -> None:
        window = TimeRange(start_seconds=10.0, end_seconds=25.5)
        assert window.duration_seconds == 15.5

    def test_contains(self) -> None:
        window = TimeRange(start_seconds=10.0, end_seconds=20.0)
        assert window.contains(15.0)
        assert not window.contains(20.1)

    def test_rejects_inverted_range(self) -> None:
        with pytest.raises(ValueError):
            TimeRange(start_seconds=20.0, end_seconds=10.0)


class TestPitchCoordinate:
    def test_defaults_to_ground_level(self) -> None:
        assert PitchCoordinate(x=10.0, y=20.0).z == 0.0


class TestPage:
    def test_rejects_excessive_limit(self) -> None:
        with pytest.raises(ValueError):
            Page(limit=Page.MAX_LIMIT + 1)

    def test_rejects_negative_offset(self) -> None:
        with pytest.raises(ValueError):
            Page(offset=-1)


class TestIdentifiersAndTime:
    def test_new_id_is_unique(self) -> None:
        assert new_id() != new_id()
        assert isinstance(new_id(), uuid.UUID)

    def test_utcnow_is_timezone_aware(self) -> None:
        assert utcnow().tzinfo is not None
