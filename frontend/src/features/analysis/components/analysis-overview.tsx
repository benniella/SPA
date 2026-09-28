"use client";

import Link from "next/link";

import { ButtonLink } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PlannedState } from "@/components/ui/states";
import { useOrganizationId } from "@/features/auth/session";
import { useApiQuery } from "@/hooks/use-api-query";
import { listVideos } from "@/services/videos";
import { listAnalysisRuns } from "@/services/analysis";
import { analysisStatusLabels } from "@/types/domain";
import type { AnalysisRun, AnalysisRunStatus } from "@/types/api";

const MAX_PAGE = 200;

export function AnalysisOverview() {
  const organizationId = useOrganizationId();

  const videos = useApiQuery(
    (options) => listVideos(organizationId ?? "", { limit: MAX_PAGE }, options),
    `analysis-videos:${organizationId}`,
    organizationId !== null,
  );

  if (organizationId === null) {
    return (
      <PlannedState
        title="No workspace selected"
        description="Analysis runs belong to an organization. Choose a workspace to see its processing history."
      />
    );
  }

  if (videos.state.status === "loading") return <LoadingState label="Loading analysis" rows={3} />;
  if (videos.state.status === "error") {
    return <ErrorState error={videos.state.error} onRetry={videos.reload} />;
  }

  const records = videos.state.data.items;

  return (
    <div className="stack stack-7">
      <section aria-labelledby="analysis-status-heading" className="stack stack-5">
        <h2 id="analysis-status-heading" className="heading-subsection">
          Processing
        </h2>

        <div className="state-block" data-tone="placeholder">
          <h3 className="state-title">The analysis pipeline is not implemented</h3>
          <p className="state-text">
            SPA is designed to turn footage into structured performance data through five stages —
            upload, detect, track, analyse and understand. Detection, tracking, pose estimation and
            metric calculation are not available yet. Nothing on this platform computes a
            performance number yet.
          </p>
        </div>

        <div className="stack stack-3">
          <h3 className="heading-card">Stage vocabulary</h3>
          <p className="text-caption">
            A run&rsquo;s status is one of the values below. The labels come from the same mapping
            the run list uses, so a status can never be shown under two different names.
          </p>
          <ul className="analysis-views" style={{ marginTop: "var(--space-3)" }}>
            {ANALYSIS_STATUSES.map((status) => (
              <li key={status} className="analysis-view">
                <span className="text-label">{analysisStatusLabels[status]}</span>
                <span className="text-micro">{status}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section aria-labelledby="analysis-runs-heading" className="stack stack-4">
        <h2 id="analysis-runs-heading" className="heading-subsection">
          Runs in this workspace
        </h2>

        <PlannedState
          title="Runs are listed per video"
          description={
            <>
              <p>
                The analysis-run endpoint requires a video, so there is no workspace-wide run list
                to show. {describesVideos(records.length)}
              </p>
              <p className="text-caption" style={{ marginTop: "var(--space-3)" }}>
                Open a video to see the runs queued against it. Until the pipeline exists, that list
                is empty for every recording.
              </p>
            </>
          }
        />

        {records.length > 0 ? (
          <ul className="ruled-list">
            {records.slice(0, 10).map((video) => (
              <li key={video.id} className="ruled-item">
                <Link className="app-row-link" href={`/videos/${encodeURIComponent(video.id)}`}>
                  {video.original_filename}
                </Link>
                <span className="app-row-meta">No runs</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="state-block" data-tone="empty">
            <h3 className="state-title">No videos to analyse</h3>
            <p className="state-text">
              Analysis needs footage. The video library is the entry point — recordings are attached
              to matches, and runs are queued against recordings.
            </p>
            <div className="state-actions">
              <ButtonLink href="/videos" variant="technical" size="md">
                 Go to video library
              </ButtonLink>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

const ANALYSIS_STATUSES: readonly AnalysisRunStatus[] = [
  "pending",
  "queued",
  "running",
  "succeeded",
  "partially_succeeded",
  "failed",
  "cancelled",
] as const;

function describesVideos(count: number): string {
  if (count === 0) return "This workspace has no recordings yet.";
  if (count === 1) return "This workspace has 1 recording.";
  return `This workspace has ${count} recordings in the first page of the library.`;
}

export function AnalysisRunList({ videoId }: { videoId: string }) {
  const { state, reload } = useApiQuery(
    (options) => listAnalysisRuns(videoId, { limit: MAX_PAGE }, options),
    `runs:${videoId}`,
  );

  if (state.status === "loading") return <LoadingState label="Loading analysis runs" rows={2} />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={reload} />;
  if (state.data.items.length === 0) return null;

  return (
    <ul className="ruled-list">
      {state.data.items.map((run) => (
        <li key={run.id} className="ruled-item">
          <Link className="app-row-link" href={`/analysis/${encodeURIComponent(run.id)}`}>
            Run {run.id.slice(0, 8)}
          </Link>
          <RunStatus run={run} />
        </li>
      ))}
    </ul>
  );
}

export function RunStatus({ run }: { run: AnalysisRun }) {
  const inFlight = run.status === "running" || run.status === "queued" || run.status === "pending";

  return (
    <span className="row-center">
      <span className="text-caption">{analysisStatusLabels[run.status]}</span>
      {inFlight ? (
        <span className="app-row-meta" aria-label={`${run.progress_percent} per cent complete`}>
          {Math.round(run.progress_percent)}%
        </span>
      ) : null}
    </span>
  );
}
