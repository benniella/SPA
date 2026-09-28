"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PlannedState } from "@/components/ui/states";
import { AnalysisMetricsPanel } from "@/features/analysis/components/analysis-metrics-panel";
import { AnalysisVisualizationPanel } from "@/features/analysis/components/analysis-visualization-panel";
import { RunStatus } from "@/features/analysis/components/analysis-overview";
import { useOrganizationId } from "@/features/auth/session";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { useApiQuery } from "@/hooks/use-api-query";
import { formatDateTime } from "@/lib/format";
import { cancelAnalysisRun, getAnalysisRun } from "@/services/analysis";
import { hasUsableResults, isTerminalStatus } from "@/types/domain";

export function AnalysisRunDetail({ runId }: { runId: string }) {
  const organizationId = useOrganizationId();

  const run = useApiQuery(
    (options) => getAnalysisRun(runId, organizationId ?? "", options),
    `run:${organizationId}:${runId}`,
    organizationId !== null,
  );

  const cancel = useApiMutation((input: { id: string; organizationId: string }) =>
    cancelAnalysisRun(input.id, input.organizationId),
  );

  if (organizationId === null) {
    return (
      <PlannedState
        title="No workspace selected"
        description="An analysis run belongs to an organization. Choose a workspace to open it."
      />
    );
  }

  if (run.state.status === "loading") return <LoadingState label="Loading analysis run" rows={4} />;
  if (run.state.status === "error") {
    return <ErrorState error={run.state.error} onRetry={run.reload} />;
  }

  const record = run.state.data;
  const finished = isTerminalStatus(record.status);

  return (
    <div className="stack stack-7">
      <div className="detail-grid">
        <div className="stack stack-5">
          <h2 className="heading-subsection">Run</h2>

          <dl className="fact-list">
            <Fact label="Status" value={<RunStatus run={record} />} />
            <Fact label="Progress" value={`${Math.round(record.progress_percent)}%`} />
            <Fact label="Started" value={formatDateTime(record.started_at)} />
            <Fact label="Finished" value={formatDateTime(record.finished_at)} />
            <Fact label="Created" value={formatDateTime(record.created_at)} />
            <Fact
              label="Video"
              value={
                <Link
                  className="app-row-link"
                  href={`/videos/${encodeURIComponent(record.video_id)}`}
                >
                  Open recording
                </Link>
              }
            />
            <Fact
              label="Match"
              value={
                record.match_id ? (
                  <Link
                    className="app-row-link"
                    href={`/matches/${encodeURIComponent(record.match_id)}`}
                  >
                    Open fixture
                  </Link>
                ) : (
                  "Not attached"
                )
              }
            />
          </dl>

          {record.error_message ? (
            <div className="state-block" data-tone="error" role="alert">
              <h3 className="state-title">This run did not complete</h3>
              <p className="state-text">{record.error_message}</p>
            </div>
          ) : null}
        </div>

        <div className="stack stack-4">
          {/* Cancelling only records intent — the worker owns execution, and there is
              no worker. Offering it on a finished run would 409; offering it on an
              in-flight run would set a flag nothing reads. Neither is offered. */}
          {finished ? null : (
            <div className="state-block" data-tone="placeholder">
              <h3 className="state-title">Cancellation</h3>
              <p className="state-text">
                Cancelling records the intent; cooperative cancellation by a worker is not
                implemented, because there is no worker. The control is therefore not offered.
              </p>
            </div>
          )}
        </div>
      </div>

      <section aria-labelledby="run-visualization-heading" className="stack stack-4">
        <h2 id="run-visualization-heading" className="heading-subsection">
          Visualization
        </h2>

        {hasUsableResults(record.status) ? (
          <AnalysisVisualizationPanel runId={runId} />
        ) : (
          <PlannedState
            title="Nothing to visualize yet"
            description="Visualization is derived from this run's persisted tracking observations, so it appears once the run has produced them."
            note="Positions are shown in source-video pixels. Pitch calibration is not available yet."
          />
        )}
      </section>

      <section aria-labelledby="run-output-heading" className="stack stack-4">
        <h2 id="run-output-heading" className="heading-subsection">
          Metrics
        </h2>

        {hasUsableResults(record.status) ? (
          <AnalysisMetricsPanel runId={runId} />
        ) : (
          <PlannedState
            title="No metrics for this run"
            description={
              <>
                <p>
                  Metrics are derived from this run&rsquo;s tracking data, so they exist only once
                  the run has succeeded. A run that is pending, running or failed has nothing to
                  show here.
                </p>
                <ul className="document-list" style={{ marginTop: "var(--space-4)" }}>
                  <li className="document-list-item">Distance travelled and coverage per track.</li>
                  <li className="document-list-item">Average and peak speed, and acceleration.</li>
                  <li className="document-list-item">Observation counts and confidence.</li>
                </ul>
              </>
            }
            note="Values are in source image pixels. Pitch calibration is not available yet."
          />
        )}
      </section>

      {!finished ? (
        <div>
          <Button
              variant="technical"
            size="md"
            arrow={false}
            disabled={cancel.state.status === "pending"}
            onClick={() =>
              void cancel.mutate({ id: runId, organizationId }).then(() => run.reload())
            }
          >
            {cancel.state.status === "pending" ? "Recording…" : "Record cancellation intent"}
          </Button>
        </div>
      ) : null}
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
