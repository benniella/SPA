"use client";

import { ButtonLink } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PlannedState } from "@/components/ui/states";
import { VideoStatusBadge } from "@/features/videos/components/video-library";
import { VideoProcessingPanel } from "@/features/processing";
import { useOrganizationId } from "@/features/auth/session";
import { useApiQuery } from "@/hooks/use-api-query";
import { formatBytes, formatDateTime, formatDuration } from "@/lib/format";
import { getVideo } from "@/services/videos";

export function VideoDetail({ videoId }: { videoId: string }) {
  const organizationId = useOrganizationId();

  const video = useApiQuery(
    (options) => getVideo(videoId, organizationId ?? "", options),
    `video:${organizationId}:${videoId}`,
    organizationId !== null,
  );

  if (organizationId === null) {
    return (
      <PlannedState
        title="No workspace selected"
        description="A video belongs to an organization. Choose a workspace to open it."
      />
    );
  }

  if (video.state.status === "loading") return <LoadingState label="Loading video" rows={4} />;
  if (video.state.status === "error") {
    return <ErrorState error={video.state.error} onRetry={video.reload} />;
  }

  const record = video.state.data;
  const probed = record.duration_seconds !== null || record.frame_rate !== null;

  return (
    <div className="stack stack-7">
      <div className="detail-grid">
        <div className="stack stack-5">
          <h2 className="heading-subsection">Media</h2>

          <dl className="fact-list">
            <Fact label="File name" value={record.original_filename} />
            <Fact label="Status" value={<VideoStatusBadge status={record.status} />} />
            <Fact label="Content type" value={record.content_type ?? "Unknown"} />
            <Fact label="Size" value={formatBytes(record.size_bytes)} />
            <Fact label="Duration" value={formatDuration(record.duration_seconds)} />
            <Fact
              label="Frame rate"
              value={record.frame_rate === null ? "Not probed" : `${record.frame_rate} fps`}
            />
            <Fact
              label="Resolution"
              value={
                record.width && record.height ? `${record.width} × ${record.height}` : "Not probed"
              }
            />
            <Fact label="Codec" value={record.codec ?? "Not probed"} />
            <Fact label="Uploaded" value={formatDateTime(record.created_at)} />
          </dl>

          {record.failure_reason ? (
            <div className="state-block" data-tone="error" role="alert">
              <h3 className="state-title">Processing failed</h3>
              <p className="state-text">{record.failure_reason}</p>
            </div>
          ) : null}
        </div>

        <div className="stack stack-4">
          {record.match_id ? (
            <ButtonLink
              href={`/matches/${encodeURIComponent(record.match_id)}`}
              variant="technical"
              size="md"
            >
              Open the match
            </ButtonLink>
          ) : (
            <PlannedState
              title="Not attached to a match"
              description="This recording is not linked to a fixture. Attaching it to a match is done at upload time."
            />
          )}
        </div>
      </div>

      {!probed ? (
        <PlannedState
          title="Media properties have not been read"
          description="Duration, frame rate, resolution and codec are written when a worker probes the file. No worker exists yet, so these fields are unknown rather than empty — which is why they read “not probed” instead of zero."
          note="Not available yet. This needs video processing."
        />
      ) : null}

      <section aria-labelledby="video-playback-heading" className="stack stack-4">
        <h2 id="video-playback-heading" className="heading-subsection">
          Playback
        </h2>
        <PlannedState
          title="No player in this build"
          description="SPA has no video player component. It needs a presigned download URL from storage, a player element, and frame-accurate seeking against tracking data — the last of which does not exist to seek against yet. Adding a bare <video> tag now would work for the file and fail for the product."
          note="Not available yet. This needs video processing and tracking."
        />
      </section>

      <section aria-labelledby="video-processing-heading" className="stack stack-4">
        <h2 id="video-processing-heading" className="heading-subsection">
          Processing
        </h2>
        <VideoProcessingPanel videoId={videoId} />
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
