"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { DataCell, DataRow, DataTable } from "@/components/ui/data-table";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/states";
import { useOrganizationId } from "@/features/auth/session";
import { VideoUploadPanel } from "@/features/videos/components/video-upload-panel";
import { useApiQuery } from "@/hooks/use-api-query";
import { ApiError } from "@/lib/api-errors";
import { formatBytes, formatDateTime, formatDuration } from "@/lib/format";
import { deleteVideo, listVideos } from "@/services/videos";
import { videoStatusLabels } from "@/types/domain";
import type { VideoStatus } from "@/types/api";

const MAX_PAGE = 200;

export function VideoLibrary() {
  const organizationId = useOrganizationId();
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { state, reload } = useApiQuery(
    (options) => listVideos(organizationId ?? "", { limit: MAX_PAGE }, options),
    `videos:${organizationId}`,
    organizationId !== null,
  );

  if (organizationId === null) {
    return (
      <EmptyState
        title="No workspace selected"
        description="Videos belong to an organization. Choose a workspace to see its recordings."
      />
    );
  }

  if (state.status === "loading") return <LoadingState label="Loading video library" rows={4} />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={reload} />;

  const videos = state.data.items;

  async function handleDelete(videoId: string, filename: string) {
    if (organizationId === null) return;
    if (!window.confirm(`Delete “${filename}”? This cannot be undone.`)) return;

    setDeleteError(null);
    setDeletingId(videoId);
    try {
      await deleteVideo(videoId, organizationId);
      reload();
    } catch (error) {
      setDeleteError(error instanceof ApiError ? error.message : "The video could not be deleted.");
    } finally {
      setDeletingId(null);
    }
  }

  const upload = <VideoUploadPanel onUploaded={reload} />;

  if (videos.length === 0) {
    return (
      <div className="stack stack-4">
        <EmptyState
          icon="video"
          title="No videos yet"
          description="Upload a match recording to get started. The file goes straight to object storage; SPA records it and confirms it landed."
          actions={upload}
        />
        {deleteError ? (
          <p className="text-caption" role="alert">
            {deleteError}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="stack stack-4">
      {upload}

      {deleteError ? (
        <p className="text-caption" role="alert">
          {deleteError}
        </p>
      ) : null}

      <DataTable
        caption="Videos in this workspace"
        columns={[
          { id: "file", header: "File" },
          { id: "status", header: "Status" },
          { id: "match", header: "Match", secondary: true },
          { id: "duration", header: "Duration", numeric: true, secondary: true },
          { id: "spec", header: "Frame rate", numeric: true, secondary: true },
          { id: "size", header: "Size", numeric: true, secondary: true },
          { id: "added", header: "Added", secondary: true },
          { id: "actions", header: "Actions" },
        ]}
      >
        {videos.map((video) => (
          <DataRow key={video.id}>
            <DataCell primary>
              <Link className="app-row-link" href={`/videos/${encodeURIComponent(video.id)}`}>
                {video.original_filename}
              </Link>
            </DataCell>
            <DataCell>
              <VideoStatusBadge status={video.status} />
            </DataCell>
            <DataCell secondary>
              {video.match_id ? (
                <Link
                  className="app-row-link"
                  href={`/matches/${encodeURIComponent(video.match_id)}`}
                >
                  Open match
                </Link>
              ) : (
                <span className="app-row-meta">Unattached</span>
              )}
            </DataCell>
            <DataCell numeric secondary>
              {formatDuration(video.duration_seconds)}
            </DataCell>
            <DataCell numeric secondary>
              {video.frame_rate === null ? "—" : `${video.frame_rate} fps`}
            </DataCell>
            <DataCell numeric secondary>
              {formatBytes(video.size_bytes)}
            </DataCell>
            <DataCell secondary>{formatDateTime(video.created_at)}</DataCell>
            <DataCell>
              <Button
                variant="technical"
                size="sm"
                loading={deletingId === video.id}
                loadingLabel="Deleting"
                onClick={() => void handleDelete(video.id, video.original_filename)}
              >
                Delete
              </Button>
            </DataCell>
          </DataRow>
        ))}
      </DataTable>

      <p className="text-caption">
        {videos.length === 1 ? "1 recording" : `${videos.length} recordings`} in this workspace.
      </p>
    </div>
  );
}

export function VideoStatusBadge({ status }: { status: VideoStatus }) {
  const tone: Record<VideoStatus, "neutral" | "info" | "success" | "danger"> = {
    pending: "neutral",
    uploading: "info",
    uploaded: "info",
    stored: "info",
    processing: "neutral",
    ready: "success",
    failed: "danger",
  };

  return (
    <span className={`badge badge-${tone[status]}`}>
      {videoStatusLabels[status]}
      {status === "failed" ? <span className="visually-hidden"> — processing failed</span> : null}
    </span>
  );
}
