"use client";

import Link from "next/link";

import { DataCell, DataRow, DataTable } from "@/components/ui/data-table";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { StateBlock } from "@/components/ui/states";
import { AnalysisVisualizationPanel } from "@/features/analysis/components/analysis-visualization-panel";
import { formatMetricValue } from "@/features/analysis/components/visualization/format";
import { useOrganizationId } from "@/features/auth/session";
import { useApiQuery } from "@/hooks/use-api-query";
import { formatDateTime } from "@/lib/format";
import { getReport } from "@/services/reports";
import type { MetricName, ReportContent, ReportMetric, ReportTrack } from "@/types/api";

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

const REPORT_STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  generating: "Generating",
  ready: "Ready",
  failed: "Failed",
};

export function ReportDetail({ reportId }: { reportId: string }) {
  const organizationId = useOrganizationId();

  const report = useApiQuery(
    (options) => getReport(reportId, organizationId ?? "", options),
    `report:${organizationId}:${reportId}`,
    organizationId !== null,
  );

  if (organizationId === null) {
    return (
      <StateBlock
        title="No workspace selected"
        description="A report belongs to an organization. Choose a workspace to open it."
      />
    );
  }

  if (report.state.status === "loading") return <LoadingState label="Loading report" rows={4} />;
  if (report.state.status === "error") {
    return <ErrorState error={report.state.error} onRetry={report.reload} />;
  }

  const record = report.state.data;

  return (
    <div className="stack stack-7">
      <div className="detail-grid">
        <div className="stack stack-5">
          <h2 className="heading-subsection">Report</h2>

          <dl className="fact-list">
            <Fact label="Title" value={record.title} />
            <Fact label="Status" value={REPORT_STATUS_LABELS[record.status] ?? record.status} />
            <Fact label="Report definition" value={record.definition_version} />
            <Fact label="Created" value={formatDateTime(record.created_at)} />
            <Fact label="Generated" value={formatDateTime(record.generated_at)} />
            <Fact
              label="Analysis run"
              value={
                record.analysis_run_id ? (
                  <Link
                    className="app-row-link"
                    href={`/analysis/${encodeURIComponent(record.analysis_run_id)}`}
                  >
                    Open analysis run
                  </Link>
                ) : (
                  "Not scoped to a run"
                )
              }
            />
          </dl>

          {record.error_message ? (
            <p className="text-caption" role="alert">
              {record.error_message}
            </p>
          ) : null}
        </div>

        <div className="stack stack-4">
          <StateBlock
            title="No document to download"
            description="A report is served as structured data. A downloadable document format is not implemented yet, so there is no download control."
          />
        </div>
      </div>

      {record.status === "generating" || record.status === "draft" ? (
        <StateBlock
          title="This report is still being generated"
          description="A report is a snapshot of an analysis run's metrics. Its contents appear once generation completes."
        />
      ) : null}

      {record.status === "failed" ? (
        <StateBlock
          tone="error"
          title="This report could not be generated"
          description="Generation reads the analysis run's persisted metrics. Requesting the report again retries it in place."
        />
      ) : null}

      {record.content ? <ReportBody content={record.content} runId={record.analysis_run_id} /> : null}
    </div>
  );
}

function ReportBody({ content, runId }: { content: ReportContent; runId: string | null }) {
  const overview = content.overview;

  return (
    <div className="stack stack-7">
      <section aria-labelledby="report-overview-heading" className="stack stack-4">
        <h2 id="report-overview-heading" className="heading-subsection">
          Analysis overview
        </h2>

        <dl className="fact-list">
          <Fact label="Analysis status" value={overview.analysis_status} />
          <Fact label="Video" value={overview.video_filename} />
          <Fact label="Analysed" value={formatDateTime(overview.analysis_created_at)} />
          <Fact label="Source frame" value={frameLabel(overview)} />
          <Fact label="Tracks" value={overview.track_count.toLocaleString()} />
          <Fact label="Observations" value={overview.observation_count.toLocaleString()} />
          <Fact label="Metric definition" value={overview.metric_definition_version} />
        </dl>

        <p className="text-caption">
          Analysis measurements are reported in source-video space (pixels). Pitch calibration is not
          available, so nothing here is a physical distance or speed.
        </p>
      </section>

      <section aria-labelledby="report-tracks-heading" className="stack stack-4">
        <h2 id="report-tracks-heading" className="heading-subsection">
          Track summary
        </h2>

        {content.tracks.length === 0 ? (
          <StateBlock
            title="No track metrics in this report"
            description="The analysis run produced no per-track metrics, so the report has no track summary."
          />
        ) : (
          <DataTable
            caption="Derived metrics for each tracked object in this report"
            columns={[
              { id: "track", header: "Track", numeric: true },
              ...TRACK_METRICS.map((metric) => ({
                id: metric.name,
                header: metric.label,
                numeric: true,
                secondary: true,
              })),
            ]}
          >
            {content.tracks.map((track) => (
              <DataRow key={track.track_id}>
                <DataCell numeric primary>
                  {track.track_id}
                </DataCell>
                {TRACK_METRICS.map((metric) => (
                  <DataCell key={metric.name} numeric secondary>
                    {formatReportMetric(findMetric(track, metric.name))}
                  </DataCell>
                ))}
              </DataRow>
            ))}
          </DataTable>
        )}
      </section>

      <section aria-labelledby="report-observations-heading" className="stack stack-4">
        <h2 id="report-observations-heading" className="heading-subsection">
          Data observations
        </h2>

        {content.observations.length === 0 ? (
          <StateBlock
            title="No observations to report"
            description="Each observation names the track holding the highest measured value for one metric. None could be derived from this run's available metrics."
          />
        ) : (
          <ul className="ruled-list">
            {content.observations.map((observation) => (
              <li key={observation.type} className="ruled-item">
                <span className="text-body">{observation.message}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {runId ? (
        <section aria-labelledby="report-visualization-heading" className="stack stack-4">
          <h2 id="report-visualization-heading" className="heading-subsection">
            Spatial &amp; activity analysis
          </h2>
          <AnalysisVisualizationPanel runId={runId} />
        </section>
      ) : null}

      <section aria-labelledby="report-limitations-heading" className="stack stack-4">
        <h2 id="report-limitations-heading" className="heading-subsection">
          Data limitations
        </h2>

        <ul className="document-list">
          {content.limitations.map((limitation) => (
            <li key={limitation} className="document-list-item">
              {limitation}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function findMetric(track: ReportTrack, name: MetricName): ReportMetric | undefined {
  return track.metrics.find((metric) => metric.name === name);
}

function formatReportMetric(metric: ReportMetric | undefined): string {
  if (metric === undefined) return "—";
  return formatMetricValue({
    name: metric.name,
    unit: metric.unit,
    space: "source",
    availability: metric.availability,
    value: metric.value,
    sample_count: metric.sample_count,
  });
}

function frameLabel(overview: ReportContent["overview"]): string {
  if (overview.source_width === null || overview.source_height === null) {
    return "Unavailable";
  }
  return `${overview.source_width.toLocaleString()} × ${overview.source_height.toLocaleString()} px`;
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="fact">
      <dt className="fact-label">{label}</dt>
      <dd className="fact-value">{value}</dd>
    </div>
  );
}
