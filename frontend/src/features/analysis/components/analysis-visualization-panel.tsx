"use client";

import { useMemo, useState } from "react";

import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/states";
import { Tabs } from "@/components/ui/tabs";
import { ActivityTimeline } from "@/features/analysis/components/visualization/activity-timeline";
import { frameLabel } from "@/features/analysis/components/visualization/geometry";
import { HeatmapVisualization } from "@/features/analysis/components/visualization/heatmap-visualization";
import { TrackMetricsPanel } from "@/features/analysis/components/visualization/track-metrics-panel";
import { TrackPathVisualization } from "@/features/analysis/components/visualization/track-path-visualization";
import { TrackSelector } from "@/features/analysis/components/visualization/track-selector";
import { useOrganizationId } from "@/features/auth/session";
import { useApiQuery } from "@/hooks/use-api-query";
import { ApiError } from "@/lib/api-errors";
import { getRunVisualization } from "@/services/analysis";

export function AnalysisVisualizationPanel({ runId }: { runId: string }) {
  const organizationId = useOrganizationId();
  const [selectedTrackId, setSelectedTrackId] = useState<number | null>(null);

  const query = useApiQuery(
    (options) => getRunVisualization(runId, organizationId ?? "", options),
    `visualization:${organizationId}:${runId}`,
    organizationId !== null,
  );

  const extentLabel = useMemo(
    () => (query.state.status === "success" ? frameLabel(query.state.data.frame) : ""),
    [query.state],
  );

  if (organizationId === null) return null;

  if (query.state.status === "loading") {
    return <LoadingState label="Loading visualization" rows={4} />;
  }

  if (query.state.status === "error") {
    if (query.state.error instanceof ApiError && query.state.error.code === "conflict") {
      return (
        <EmptyState
          title="Tracking data is not available yet"
          description="Visualization is derived from this run's persisted tracking observations. The run has not produced any, so there is nothing to draw."
        />
      );
    }
    return <ErrorState error={query.state.error} onRetry={query.reload} />;
  }

  const data = query.state.data;

  if (data.observation_count === 0 || data.paths.length === 0) {
    return (
      <EmptyState
        title="No track observations were produced"
        description="This run completed without recording any tracked positions, so no track path, spatial density or activity timeline can be drawn."
      />
    );
  }

  return (
    <div className="stack stack-6 viz-panel">
      <dl className="fact-list">
        <Fact label="Coordinate space" value="Source-video pixels — not calibrated" />
        <Fact label="Source frame" value={extentLabel} />
        <Fact label="Tracks" value={data.track_count.toLocaleString()} />
        <Fact label="Observations" value={data.observation_count.toLocaleString()} />
      </dl>

      <p className="text-caption">
        Positions are the pixel coordinates the tracker recorded, so a coordinate means a position
        in the source video frame — SPA has no pitch calibration, and these are not metres.
      </p>

      <TrackSelector
        tracks={data.paths}
        selectedTrackId={selectedTrackId}
        onSelect={setSelectedTrackId}
      />

      <Tabs
        label="Analysis visualization"
        items={[
          {
            id: "paths",
            label: "Track paths",
            content: (
              <TrackPathVisualization
                visualization={data}
                selectedTrackId={selectedTrackId}
                onSelectTrack={setSelectedTrackId}
              />
            ),
          },
          {
            id: "density",
            label: "Spatial density",
            content: (
              <HeatmapVisualization visualization={data} selectedTrackId={selectedTrackId} />
            ),
          },
          {
            id: "timeline",
            label: "Activity",
            content: <ActivityTimeline visualization={data} selectedTrackId={selectedTrackId} />,
          },
        ]}
      />

      <section aria-labelledby="track-metrics-heading" className="stack stack-4">
        <h3 id="track-metrics-heading" className="heading-card">
          Track metrics
        </h3>
        <TrackMetricsPanel visualization={data} selectedTrackId={selectedTrackId} />
      </section>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="fact">
      <dt className="fact-label">{label}</dt>
      <dd className="fact-value">{value}</dd>
    </div>
  );
}
