from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.metrics.types import (
    MetricName,
    MetricSpace,
    MetricUnit,
)
from app.domain.reports.content import (
    DataObservation,
    MetricSummary,
    ObservationType,
    ReportContent,
    ReportOverview,
    TrackSummary,
    content_from_dict,
    content_to_dict,
)
from app.domain.reports.export import render_report_html
from app.domain.shared import AnalysisRunId


def content(*, track_metrics: tuple[MetricSummary, ...] | None = None) -> ReportContent:
    return ReportContent(
        definition_version="v1",
        overview=ReportOverview(
            analysis_run_id=AnalysisRunId(uuid.uuid4()),
            analysis_status="succeeded",
            video_id=str(uuid.uuid4()),
            video_filename="match.mp4",
            match_id=None,
            analysis_created_at=datetime(2025, 1, 1, tzinfo=UTC),
            analysis_finished_at=datetime(2025, 1, 1, 0, 2, tzinfo=UTC),
            source_width=1920,
            source_height=1080,
            observation_count=120,
            track_count=1,
            metric_definition_version="v1",
            space=MetricSpace.SOURCE,
        ),
        tracks=(
            TrackSummary(
                track_id=1,
                space=MetricSpace.SOURCE,
                metrics=track_metrics
                if track_metrics is not None
                else (
                    MetricSummary(
                        name=MetricName.OBSERVATION_COUNT,
                        unit=MetricUnit.COUNT,
                        value=120.0,
                        sample_count=120,
                    ),
                    MetricSummary(
                        name=MetricName.DISPLACEMENT,
                        unit=MetricUnit.PIXELS,
                        value=1240.0,
                        sample_count=119,
                    ),
                    MetricSummary(
                        name=MetricName.PEAK_SPEED,
                        unit=MetricUnit.PIXELS_PER_SECOND,
                        value=None,
                        sample_count=1,
                    ),
                ),
            ),
        ),
        observations=(
            DataObservation(
                type=ObservationType.HIGHEST_OBSERVATION_COUNT,
                track_ids=(1,),
                metric_name=MetricName.OBSERVATION_COUNT,
                unit=MetricUnit.COUNT,
                space=MetricSpace.SOURCE,
                value=120.0,
                message="Track 1 has the highest observed observation count in this analysis: 120.",
            ),
        ),
        limitations=(
            "Measurements are reported in source-video space (pixels), not physical distance.",
        ),
    )


class TestDeterministicRendering:
    def test_the_same_content_renders_identical_markup(self) -> None:
        body = content()

        first = render_report_html(body, title="Report", generated_at="2025-01-01T00:05:00+00:00")
        second = render_report_html(body, title="Report", generated_at="2025-01-01T00:05:00+00:00")

        assert first == second

    def test_the_document_contains_the_report_data(self) -> None:
        html = render_report_html(content(), title="Report", generated_at="2025-01-01T00:05:00+00:00")

        assert "match.mp4" in html
        assert "1,920 × 1,080 px" in html  # noqa: RUF001 - matches the rendered dimension string
        assert "1,240 px" in html
        assert "120" in html
        assert "Track 1 has the highest observed observation count in this analysis: 120." in html

    def test_an_unavailable_metric_is_rendered_as_unavailable(self) -> None:
        html = render_report_html(content(), title="Report", generated_at="2025-01-01T00:05:00+00:00")

        assert "Unavailable" in html
        assert "0 px/s" not in html

    def test_the_document_states_the_source_space_limitation(self) -> None:
        html = render_report_html(content(), title="Report", generated_at="2025-01-01T00:05:00+00:00")

        assert "source-video space" in html

    def test_the_document_carries_no_scripting_or_external_assets(self) -> None:
        html = render_report_html(content(), title="Report", generated_at="2025-01-01T00:05:00+00:00")

        assert "<script" not in html
        assert "http://" not in html
        assert "https://" not in html

    def test_the_title_is_escaped(self) -> None:
        html = render_report_html(
            content(), title="<script>alert(1)</script>", generated_at="2025-01-01T00:05:00+00:00"
        )

        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html


class TestSerialisationRoundTrip:
    def test_content_survives_a_dict_round_trip(self) -> None:
        original = content()

        restored = content_from_dict(content_to_dict(original))

        assert restored == original
