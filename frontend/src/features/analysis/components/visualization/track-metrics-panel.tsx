"use client";

import { formatMetricValue, metricOf } from "@/features/analysis/components/visualization/format";
import type { MetricName, RunVisualization, TrackMetrics } from "@/types/api";

const TRACK_METRICS: ReadonlyArray<{ name: MetricName; label: string }> = [
  { name: "observation_count", label: "Observations" },
  { name: "duration", label: "Duration" },
  { name: "coverage", label: "Coverage" },
  { name: "displacement", label: "Displacement" },
  { name: "average_speed", label: "Average speed" },
  { name: "peak_speed", label: "Peak speed" },
  { name: "average_acceleration", label: "Average acceleration" },
  { name: "peak_acceleration", label: "Peak acceleration" },
  { name: "mean_confidence", label: "Mean confidence" },
];

interface TrackMetricsPanelProps {
  readonly visualization: RunVisualization;
  readonly selectedTrackId: number | null;
}

export function TrackMetricsPanel({ visualization, selectedTrackId }: TrackMetricsPanelProps) {
  const track = findTrack(visualization, selectedTrackId);

  if (selectedTrackId === null) {
    return <p className="text-caption">Select a track to see the metrics derived for it.</p>;
  }

  if (!track) {
    return (
      <p className="text-caption">
        No metrics were derived for track {selectedTrackId}. Metrics exist only once the metrics
        stage has run for this analysis.
      </p>
    );
  }

  return (
    <dl className="fact-list">
      {TRACK_METRICS.map((metric) => (
        <div key={metric.name} className="fact">
          <dt className="fact-label">{metric.label}</dt>
          <dd className="fact-value">{formatMetricValue(metricOf(track, metric.name))}</dd>
        </div>
      ))}
    </dl>
  );
}

function findTrack(
  visualization: RunVisualization,
  selectedTrackId: number | null,
): TrackMetrics | undefined {
  if (selectedTrackId === null) return undefined;
  return visualization.metrics.tracks.find((track) => track.track_id === selectedTrackId);
}
