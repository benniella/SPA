"""Performance-metrics domain tests."""

from __future__ import annotations

import pytest

from app.domain.analysis.entities import AnalysisRunStatus
from app.domain.analysis.metrics import (
    AnalysisReadiness,
    HeatmapGrid,
    IntensityZoneBreakdown,
    MetricCategory,
    MetricScope,
    PerformanceMetric,
    TeamShapeSample,
)
from app.domain.shared import (
    AnalysisRunId,
    MetricValue,
    OrganizationId,
    Percentage,
    PitchCoordinate,
    PlayerId,
    TeamId,
    TrackingDatasetId,
    new_id,
)


class TestMetricScope:
    def test_rejects_unknown_scope(self) -> None:
        with pytest.raises(ValueError):
            MetricScope("referee")


class TestMetricCategory:
    @pytest.mark.parametrize(
        "category",
        ["movement", "workload", "intensity", "team_shape", "possession", "physical"],
    )
    def test_accepts_the_metric_vocabulary(self, category: str) -> None:
        assert str(MetricCategory(category)) == category

    def test_rejects_unknown_category(self) -> None:
        with pytest.raises(ValueError):
            MetricCategory("vibes")


class TestPerformanceMetric:
    def _metric(self, scope: str, **kwargs: object) -> PerformanceMetric:
        return PerformanceMetric(
            organization_id=OrganizationId(new_id()),
            analysis_run_id=AnalysisRunId(new_id()),
            scope=MetricScope(scope),
            category=MetricCategory("movement"),
            metric=MetricValue(name="distance_covered", value=9500.0, unit="m"),
            **kwargs,  # type: ignore[arg-type]
        )

    def test_player_metric_requires_a_player(self) -> None:
        with pytest.raises(ValueError):
            self._metric("player")

    def test_team_metric_requires_a_team(self) -> None:
        with pytest.raises(ValueError):
            self._metric("team")

    def test_player_metric_accepts_a_player(self) -> None:
        metric = self._metric("player", player_id=PlayerId(new_id()))
        assert metric.name == "distance_covered"
        assert metric.value == 9500.0

    def test_match_metric_needs_no_subject(self) -> None:
        assert self._metric("match").scope == MetricScope.MATCH


class TestHeatmapGrid:
    def test_requires_cells_matching_dimensions(self) -> None:
        with pytest.raises(ValueError):
            HeatmapGrid(
                organization_id=OrganizationId(new_id()),
                analysis_run_id=AnalysisRunId(new_id()),
                tracking_dataset_id=TrackingDatasetId(new_id()),
                rows=2,
                cols=3,
                cells=[1.0, 2.0],
            )

    def test_reads_row_major_cells(self) -> None:
        grid = HeatmapGrid(
            organization_id=OrganizationId(new_id()),
            analysis_run_id=AnalysisRunId(new_id()),
            tracking_dataset_id=TrackingDatasetId(new_id()),
            rows=2,
            cols=2,
            cells=[1.0, 2.0, 3.0, 4.0],
        )
        assert grid.value_at(0, 0) == 1.0
        assert grid.value_at(1, 1) == 4.0

    def test_rejects_out_of_range_reads(self) -> None:
        grid = HeatmapGrid(
            organization_id=OrganizationId(new_id()),
            analysis_run_id=AnalysisRunId(new_id()),
            tracking_dataset_id=TrackingDatasetId(new_id()),
            rows=1,
            cols=1,
            cells=[1.0],
        )
        with pytest.raises(IndexError):
            grid.value_at(1, 0)


class TestTeamShapeSample:
    def test_validates_compactness(self) -> None:
        with pytest.raises(ValueError):
            TeamShapeSample(
                timestamp_seconds=1.0,
                team_id=TeamId(new_id()),
                centroid=PitchCoordinate(x=0.0, y=0.0),
                width_metres=30.0,
                depth_metres=25.0,
                compactness=1.5,
                player_count=11,
            )


class TestIntensityZoneBreakdown:
    def test_requires_one_more_share_than_thresholds(self) -> None:
        # A single threshold partitions time into two zones, so three shares for
        # one threshold is inconsistent.
        with pytest.raises(ValueError):
            IntensityZoneBreakdown(
                thresholds=(5.0,),
                share_by_zone=(Percentage(50.0), Percentage(30.0), Percentage(20.0)),
            )

    def test_rejects_unsorted_thresholds(self) -> None:
        # Out-of-order thresholds would silently mislabel every zone, so this is
        # rejected rather than tolerated.
        with pytest.raises(ValueError):
            IntensityZoneBreakdown(
                thresholds=(7.0, 5.0),
                share_by_zone=(Percentage(40.0), Percentage(35.0), Percentage(25.0)),
            )

    def test_accepts_a_consistent_breakdown(self) -> None:
        breakdown = IntensityZoneBreakdown(
            thresholds=(5.0, 7.0),
            share_by_zone=(Percentage(40.0), Percentage(35.0), Percentage(25.0)),
        )
        assert len(breakdown.share_by_zone) == 3
        assert breakdown.total_share == 100.0

    def test_total_share_is_exposed_but_not_enforced(self) -> None:
        # Rounding across zones is legitimate real data, so the constructor does
        # not demand an exact 100; callers that need exactness can check.
        breakdown = IntensityZoneBreakdown(
            thresholds=(5.0,),
            share_by_zone=(Percentage(33.3), Percentage(33.3)),
        )
        assert breakdown.total_share == pytest.approx(66.6)


class TestAnalysisReadiness:
    def test_success_and_partial_success_are_usable(self) -> None:
        for status in ("succeeded", "partially_succeeded"):
            readiness = AnalysisReadiness(
                run_id=AnalysisRunId(new_id()),
                status=AnalysisRunStatus(status),
            )
            assert readiness.has_usable_results
            assert not readiness.is_in_flight

    def test_running_is_in_flight(self) -> None:
        readiness = AnalysisReadiness(
            run_id=AnalysisRunId(new_id()),
            status=AnalysisRunStatus(AnalysisRunStatus.RUNNING),
        )
        assert readiness.is_in_flight
        assert not readiness.has_usable_results
