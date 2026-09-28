"use client";

import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";
import { DataCell, DataRow, DataTable } from "@/components/ui/data-table";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/states";
import { useOrganizationId } from "@/features/auth/session";
import { useApiQuery } from "@/hooks/use-api-query";
import { ApiError } from "@/lib/api-errors";
import { calculateAnalysisMetrics, getAnalysisMetrics } from "@/services/analysis";
import type { MetricName, MetricValue, TrackMetrics } from "@/types/api";

const SUMMARY_METRICS: ReadonlyArray<{ name: MetricName; label: string }> = [
  { name: "observation_count", label: "Observations" },
  { name: "duration", label: "Duration" },
  { name: "displacement", label: "Distance" },
  { name: "average_speed", label: "Average speed" },
  { name: "peak_speed", label: "Peak speed" },
  { name: "average_acceleration", label: "Average acceleration" },
  { name: "coverage", label: "Coverage" },
  { name: "mean_confidence", label: "Mean confidence" },
];

const UNIT_LABELS: Record<string, string> = {
  count: "",
  seconds: "s",
  pixels: "px",
  pixels_per_second: "px/s",
  pixels_per_second_squared: "px/s²",
};

export function AnalysisMetricsPanel({ runId }: { runId: string }) {
  const organizationId = useOrganizationId();
  const [actionError, setActionError] = useState<string | null>(null);
  const [queuing, setQueuing] = useState(false);

  const metrics = useApiQuery(
    (options) => getAnalysisMetrics(runId, organizationId ?? "", options),
    `metrics:${organizationId}:${runId}`,
    organizationId !== null,
  );

  const reload = metrics.reload;

  const onCalculate = useCallback(() => {
    setActionError(null);
    setQueuing(true);
    void calculateAnalysisMetrics(runId, organizationId ?? "")
      .then(() => reload())
      .catch((error: unknown) => {
        setActionError(
          error instanceof ApiError ? error.message : "Metric calculation could not be queued.",
        );
      })
      .finally(() => setQueuing(false));
  }, [runId, organizationId, reload]);

  if (organizationId === null) return null;

  const calculateAction = (
    <div>
      <Button
          variant="technical"
        size="md"
        arrow={false}
        disabled={queuing}
        onClick={onCalculate}
      >
        {queuing ? "Queuing…" : "Calculate metrics"}
      </Button>
    </div>
  );

  if (metrics.state.status === "loading") {
    return <LoadingState label="Loading metrics" rows={3} />;
  }

  if (metrics.state.status === "error") {
    // A 409 means the metrics stage has not run yet, which is a state to act on
    // rather than an error to report.
    if (metrics.state.error instanceof ApiError && metrics.state.error.code === "conflict") {
      return (
        <div className="stack stack-4">
          <EmptyState
            title="No metrics calculated yet"
            description="Metrics are derived from this run's tracking data. None has been calculated for this run, so there is nothing to show."
            actions={calculateAction}
          />
          {actionError ? (
            <p className="text-caption" role="alert">
              {actionError}
            </p>
          ) : null}
        </div>
      );
    }
    return <ErrorState error={metrics.state.error} onRetry={reload} />;
  }

  const data = metrics.state.data;

  if (data.track_count === 0) {
    return (
      <div className="stack stack-4">
        <EmptyState
          title="No metrics available"
          description="This run has produced no metrics for any track. A track needs at least one observation before anything can be derived from it."
          actions={calculateAction}
        />
        {actionError ? (
          <p className="text-caption" role="alert">
            {actionError}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="stack stack-5">
      <dl className="fact-list">
        <Fact label="Tracks" value={data.track_count.toLocaleString()} />
        <Fact label="Metric definition" value={data.definition_version} />
        <Fact
          label="Coordinate space"
          value={
            data.space === "calibrated"
              ? "Calibrated (physical units)"
              : "Source image pixels — not calibrated"
          }
        />
      </dl>

      {data.space === "source" ? (
        <p className="text-caption">
          Distances and speeds are measured in image pixels. SPA has no pitch calibration yet, so no
          physical distance or speed is reported — pixels are not metres.
        </p>
      ) : null}

      <div className="stack stack-3">
        <h3 className="heading-card">Per track</h3>
        <DataTable
          caption="Derived metrics for each tracked object in this run"
          columns={[
            { id: "track", header: "Track", numeric: true },
            ...SUMMARY_METRICS.map((metric) => ({
              id: metric.name,
              header: metric.label,
              numeric: true,
            })),
          ]}
        >
          {data.tracks.map((track) => (
            <DataRow key={track.track_id}>
              <DataCell numeric>{track.track_id}</DataCell>
              {SUMMARY_METRICS.map((metric) => (
                <DataCell key={metric.name} numeric>
                  {formatMetric(findMetric(track, metric.name))}
                </DataCell>
              ))}
            </DataRow>
          ))}
        </DataTable>
      </div>

      {actionError ? (
        <p className="text-caption" role="alert">
          {actionError}
        </p>
      ) : null}
    </div>
  );
}

function findMetric(track: TrackMetrics, name: MetricName): MetricValue | undefined {
  return track.metrics.find((metric) => metric.name === name);
}

function formatMetric(metric: MetricValue | undefined): string {
  if (!metric) return "—";
  if (metric.availability === "unavailable" || metric.value === null) return "Unavailable";
  return `${formatNumber(metric.value)}${suffix(metric.unit)}`;
}

function suffix(unit: string): string {
  const label = UNIT_LABELS[unit];
  return label ? ` ${label}` : "";
}

function formatNumber(value: number): string {
  if (Number.isInteger(value)) return value.toLocaleString();
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="fact">
      <dt className="fact-label">{label}</dt>
      <dd className="fact-value">{value}</dd>
    </div>
  );
}
