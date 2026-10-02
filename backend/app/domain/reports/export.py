from __future__ import annotations

from datetime import datetime

from app.domain.metrics.types import MetricName, MetricUnit
from app.domain.reports.content import MetricSummary, ReportContent, TrackSummary

EXPORT_DEFINITION_VERSION = "v1"

#: The order metrics are listed in a track's summary, so every report renders its
#: tracks the same way regardless of the order they were stored in.
METRIC_ORDER: tuple[MetricName, ...] = (
    MetricName.OBSERVATION_COUNT,
    MetricName.DURATION,
    MetricName.COVERAGE,
    MetricName.DISPLACEMENT,
    MetricName.AVERAGE_SPEED,
    MetricName.PEAK_SPEED,
    MetricName.AVERAGE_ACCELERATION,
    MetricName.PEAK_ACCELERATION,
    MetricName.MEAN_CONFIDENCE,
)

METRIC_LABELS: dict[MetricName, str] = {
    MetricName.OBSERVATION_COUNT: "Observations",
    MetricName.DURATION: "Duration",
    MetricName.COVERAGE: "Coverage",
    MetricName.DISPLACEMENT: "Displacement",
    MetricName.AVERAGE_SPEED: "Average speed",
    MetricName.PEAK_SPEED: "Peak speed",
    MetricName.AVERAGE_ACCELERATION: "Average acceleration",
    MetricName.PEAK_ACCELERATION: "Peak acceleration",
    MetricName.MEAN_CONFIDENCE: "Mean confidence",
    MetricName.MIN_CONFIDENCE: "Minimum confidence",
    MetricName.MAX_CONFIDENCE: "Maximum confidence",
}

UNIT_SUFFIXES: dict[MetricUnit, str] = {
    MetricUnit.COUNT: "",
    MetricUnit.SECONDS: " s",
    MetricUnit.PIXELS: " px",
    MetricUnit.PIXELS_PER_SECOND: " px/s",
    MetricUnit.PIXELS_PER_SECOND_SQUARED: " px/s²",
}


def render_report_html(content: ReportContent, *, title: str, generated_at: str) -> str:
    """Render a report body as a self-contained, deterministic HTML document.

    The output is a pure function of the report's stored snapshot: the same
    content always produces byte-identical markup, so an exported document can be
    compared and re-generated. It carries no scripting, no external assets and no
    browser-only controls, so it is safe to store and to open offline.
    """
    sections = [
        _header(title, generated_at, content.definition_version),
        _overview_section(content),
        _tracks_section(content.tracks),
        _observations_section(content),
        _limitations_section(content),
    ]
    body = "\n".join(sections)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{_escape(title)}</title>\n"
        f"<style>{_STYLESHEET}</style>\n"
        "</head>\n<body>\n"
        f"{body}\n"
        "</body>\n</html>\n"
    )


def _header(title: str, generated_at: str, definition_version: str) -> str:
    return (
        '<header class="report-header">\n'
        '<p class="eyebrow">SPA — Sport Performance Analysis</p>\n'
        f"<h1>{_escape(title)}</h1>\n"
        '<p class="meta">Generated '
        f"{_escape(generated_at)} · report definition {_escape(definition_version)}</p>\n"
        "</header>"
    )


def _overview_section(content: ReportContent) -> str:
    overview = content.overview
    width, height = overview.source_width, overview.source_height
    frame = (
        f"{width:,} × {height:,} px"  # noqa: RUF001 - the multiplication sign matches the UI
        if width is not None and height is not None
        else "Unavailable"
    )
    rows = [
        ("Analysis status", overview.analysis_status),
        ("Video", overview.video_filename),
        ("Analysed", _iso(overview.analysis_created_at)),
        ("Analysis finished", _iso(overview.analysis_finished_at)),
        ("Source frame", frame),
        ("Tracks", f"{overview.track_count:,}"),
        ("Observations", f"{overview.observation_count:,}"),
        ("Metric definition", overview.metric_definition_version),
    ]
    facts = "\n".join(
        f'<div class="fact"><dt>{_escape(label)}</dt><dd>{_escape(value)}</dd></div>'
        for label, value in rows
    )
    return (
        '<section class="section">\n<h2>Analysis overview</h2>\n'
        f'<dl class="facts">\n{facts}\n</dl>\n'
        '<p class="note">Analysis measurements are reported in source-video space '
        "(pixels). Pitch calibration is not available, so nothing here is a physical "
        "distance or speed.</p>\n</section>"
    )


def _tracks_section(tracks: tuple[TrackSummary, ...]) -> str:
    if not tracks:
        return (
            '<section class="section">\n<h2>Track summary</h2>\n'
            '<p class="empty">The analysis run produced no per-track metrics.</p>\n</section>'
        )

    head = "".join(f'<th scope="col">{_escape(METRIC_LABELS[name])}</th>' for name in METRIC_ORDER)
    body_rows = "\n".join(
        "<tr>"
        + f'<th scope="row">{track.track_id}</th>'
        + "".join(f"<td>{_escape(_metric_text(track, name))}</td>" for name in METRIC_ORDER)
        + "</tr>"
        for track in tracks
    )
    return (
        '<section class="section">\n<h2>Track summary</h2>\n'
        '<div class="table-wrap">\n<table>\n'
        f'<thead><tr><th scope="col">Track</th>{head}</tr></thead>\n'
        f"<tbody>\n{body_rows}\n</tbody>\n"
        "</table>\n</div>\n</section>"
    )


def _observations_section(content: ReportContent) -> str:
    if not content.observations:
        return (
            '<section class="section">\n<h2>Data observations</h2>\n'
            '<p class="empty">No observation could be derived from the run\'s available '
            "metrics.</p>\n</section>"
        )
    items = "\n".join(
        f"<li>{_escape(observation.message)}</li>" for observation in content.observations
    )
    return (
        f'<section class="section">\n<h2>Data observations</h2>\n<ul>\n{items}\n</ul>\n</section>'
    )


def _limitations_section(content: ReportContent) -> str:
    items = "\n".join(f"<li>{_escape(text)}</li>" for text in content.limitations)
    return f'<section class="section">\n<h2>Data limitations</h2>\n<ul>\n{items}\n</ul>\n</section>'


def _metric_text(track: TrackSummary, name: MetricName) -> str:
    metric: MetricSummary | None = _find(track, name)
    if metric is None:
        return "—"
    if not metric.is_available or metric.value is None:
        return "Unavailable"
    return f"{_number(metric.value)}{UNIT_SUFFIXES[metric.unit]}"


def _find(track: TrackSummary, name: MetricName) -> MetricSummary | None:
    for metric in track.metrics:
        if metric.name is name:
            return metric
    return None


def _number(value: float) -> str:
    if value.is_integer():
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value is not None else "Unavailable"


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


_STYLESHEET = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 48px 40px; background: #090A0B; color: #F5F5F5;
  font-family: Inter, "Helvetica Neue", Arial, sans-serif; font-size: 14px; line-height: 1.55;
}
h1 { font-family: "Space Grotesk", Inter, sans-serif; font-size: 26px; margin: 4px 0 6px; }
h2 {
  font-family: "Space Grotesk", Inter, sans-serif; font-size: 16px; letter-spacing: .04em;
  text-transform: uppercase; color: #19E68C; margin: 0 0 12px;
}
.report-header { border-bottom: 1px solid #292D31; padding-bottom: 20px; margin-bottom: 32px; }
.eyebrow {
  font-family: "IBM Plex Mono", monospace; font-size: 11px; letter-spacing: .18em;
  text-transform: uppercase; color: #A5ABB2; margin: 0;
}
.meta { font-family: "IBM Plex Mono", monospace; font-size: 11px; color: #A5ABB2; margin: 0; }
.section { margin-bottom: 36px; break-inside: avoid; }
.facts {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px 24px; margin: 0;
}
.fact { border-top: 1px solid #292D31; padding-top: 8px; }
.fact dt {
  font-family: "IBM Plex Mono", monospace; font-size: 10px; letter-spacing: .12em;
  text-transform: uppercase; color: #A5ABB2;
}
.fact dd { margin: 2px 0 0; font-size: 14px; }
.note, .empty { font-size: 12px; color: #A5ABB2; margin: 16px 0 0; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 12px; }
th, td {
  text-align: right; padding: 8px 10px; border-bottom: 1px solid #292D31; white-space: nowrap;
}
th:first-child, td:first-child { text-align: left; }
thead th {
  font-family: "IBM Plex Mono", monospace; font-size: 10px; letter-spacing: .1em;
  text-transform: uppercase; color: #A5ABB2;
}
tbody th { font-family: "IBM Plex Mono", monospace; color: #19E68C; font-weight: 500; }
ul { margin: 0; padding-left: 18px; }
li { margin-bottom: 8px; }
@media print {
  body { background: #FFFFFF; color: #090A0B; padding: 0; }
  h2 { color: #00B96B; }
  .fact dt, .eyebrow, .meta, thead th { color: #4A5058; }
  th, td { border-bottom: 1px solid #D8DADD; }
  .report-header { border-bottom: 1px solid #D8DADD; }
  .table-wrap { overflow: visible; }
}
@media (max-width: 640px) {
  body { padding: 24px 16px; }
  .facts { grid-template-columns: 1fr; }
}
"""
