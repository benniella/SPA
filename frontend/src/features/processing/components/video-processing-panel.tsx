"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { useOrganizationId } from "@/features/auth/session";
import { useProcessingEvents } from "@/features/processing/events-provider";
import { useApiQuery } from "@/hooks/use-api-query";
import { ApiError } from "@/lib/api-errors";
import { formatDateTime } from "@/lib/format";
import { getVideoProcessing, requestVideoProcessing } from "@/services/processing";
import { processingStatusLabels } from "@/types/domain";
import type { ProcessingJobStatus } from "@/types/api";

const PROCESSABLE: ReadonlySet<string> = new Set(["uploaded", "stored", "ready"]);

export function VideoProcessingPanel({ videoId }: { videoId: string }) {
  const organizationId = useOrganizationId();
  const events = useProcessingEvents();
  const [actionError, setActionError] = useState<string | null>(null);

  const state = useApiQuery(
    (options) => getVideoProcessing(videoId, organizationId ?? "", options),
    `processing:${organizationId}:${videoId}`,
    organizationId !== null,
  );

  const reload = state.reload;
  const reloadRef = useRef(reload);

  useEffect(() => {
    reloadRef.current = reload;
  }, [reload]);

  useEffect(() => {
    if (!events) return;
    return events.subscribe(videoId, () => {
      // The event says something changed; the read says what it is.
      reloadRef.current();
    });
  }, [events, videoId]);

  const [queuing, setQueuing] = useState(false);

  const onProcess = useCallback(() => {
    setActionError(null);
    setQueuing(true);
    void requestVideoProcessing(videoId, organizationId ?? "")
      .then(() => reloadRef.current())
      .catch((error: unknown) => {
        setActionError(
          error instanceof ApiError ? error.message : "Processing could not be queued.",
        );
      })
      .finally(() => setQueuing(false));
  }, [videoId, organizationId]);

  if (organizationId === null) return null;
  if (state.state.status === "loading")
    return <LoadingState label="Loading processing state" rows={2} />;
  if (state.state.status === "error") {
    return <ErrorState error={state.state.error} onRetry={state.reload} />;
  }

  const { video_status: videoStatus, job } = state.state.data;
  const jobStatus: ProcessingJobStatus | null = job?.status ?? null;
  const busy = jobStatus === "queued" || jobStatus === "running" || videoStatus === "processing";
  const canProcess = PROCESSABLE.has(videoStatus) && !busy;

  const { frames_processed: framesProcessed, detections, tracks } = state.state.data;

  return (
    <div className="stack stack-4">
      <dl className="fact-list">
        <Fact
          label="Processing"
          value={jobStatus ? processingStatusLabels[jobStatus] : statusLabelForVideo(videoStatus)}
        />
        {job ? <Fact label="Attempt" value={`${job.attempt} of ${job.max_attempts}`} /> : null}
        {job?.started_at ? <Fact label="Started" value={formatDateTime(job.started_at)} /> : null}
        {job?.completed_at ? (
          <Fact label="Finished" value={formatDateTime(job.completed_at)} />
        ) : null}
        {framesProcessed !== null ? (
          <Fact label="Frames processed" value={framesProcessed.toLocaleString()} />
        ) : null}
        {detections !== null ? (
          <Fact label="Detections" value={detections.toLocaleString()} />
        ) : null}
        {tracks !== null ? <Fact label="Tracks" value={tracks.toLocaleString()} /> : null}
      </dl>

      {job && jobStatus === "running" && job.progress > 0 ? (
        <div className="stack stack-2">
          <p className="text-caption">Processing — {Math.round(job.progress)}%</p>
          <div
            className="upload-progress"
            role="progressbar"
            aria-label="Processing progress"
            aria-valuenow={Math.round(job.progress)}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <span className="upload-progress__bar" style={{ width: `${job.progress}%` }} />
          </div>
        </div>
      ) : null}

      {job && jobStatus === "running" && job.progress <= 0 ? (
        <p className="text-caption" role="status">
          Processing has started. Progress is not reported yet, so no percentage is shown.
        </p>
      ) : null}

      {job && jobStatus === "failed" ? (
        <div className="state-block" data-tone="error" role="alert">
          <h3 className="state-title">Processing failed</h3>
          <p className="state-text">{job.error ?? "No reason was recorded."}</p>
        </div>
      ) : null}

      {actionError ? (
        <p className="text-caption" role="alert">
          {actionError}
        </p>
      ) : null}

      {canProcess ? (
        <div>
          <Button
              variant="technical"
            size="md"
            arrow={false}
            disabled={queuing}
            onClick={onProcess}
          >
            {queuing ? "Queuing…" : "Process this video"}
          </Button>
        </div>
      ) : null}

      {!canProcess && !busy && jobStatus === null && !PROCESSABLE.has(videoStatus) ? (
        <p className="text-caption">
          This video cannot be processed while it is {videoStatus.replace("_", " ")}.
        </p>
      ) : null}

      {events?.status === "reconnecting" ? (
        <p className="text-caption" role="status">
          Live updates are reconnecting. The state shown is read from the server.
        </p>
      ) : null}
    </div>
  );
}

function statusLabelForVideo(videoStatus: string): string {
  if (videoStatus === "ready") return "Processed";
  if (videoStatus === "processing") return "Processing";
  if (videoStatus === "failed") return "Failed";
  return "Not processed";
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="fact">
      <dt className="fact-label">{label}</dt>
      <dd className="fact-value">{value}</dd>
    </div>
  );
}
