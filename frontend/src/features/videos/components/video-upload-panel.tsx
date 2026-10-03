"use client";

import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { useOrganizationId } from "@/features/auth/session";
import { ApiError } from "@/lib/api-errors";
import { completeVideoUpload, requestVideoUpload, uploadToStorage } from "@/services/videos";

const ACCEPTED_TYPES = "video/mp4,video/quicktime,video/webm,video/x-matroska";

type UploadState =
  | { status: "idle" }
  | { status: "requesting" }
  | { status: "uploading"; filename: string; progress: number | null }
  | { status: "confirming"; filename: string }
  | { status: "error"; message: string };

export interface VideoUploadPanelProps {
  readonly onUploaded: () => void;
}

export function VideoUploadPanel({ onUploaded }: VideoUploadPanelProps) {
  const organizationId = useOrganizationId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploadState, setUploadState] = useState<UploadState>({ status: "idle" });

  const busy =
    uploadState.status === "requesting" ||
    uploadState.status === "uploading" ||
    uploadState.status === "confirming";

  async function handleFile(file: File) {
    if (organizationId === null) return;

    setUploadState({ status: "requesting" });

    let ticket;
    try {
      ticket = await requestVideoUpload({
        organization_id: organizationId,
        filename: file.name,
        content_type: file.type || null,
      });
    } catch (error) {
      setUploadState({ status: "error", message: describe(error, "Could not start the upload.") });
      return;
    }

    setUploadState({ status: "uploading", filename: file.name, progress: 0 });

    try {
      await uploadToStorage(ticket.upload_url, file, {
        onProgress: (progress) =>
          setUploadState({ status: "uploading", filename: file.name, progress }),
      });
    } catch (error) {
      setUploadState({ status: "error", message: describe(error, "The upload failed.") });
      return;
    }

    setUploadState({ status: "confirming", filename: file.name });

    try {
      await completeVideoUpload(ticket.video_id, {
        organization_id: organizationId,
        size_bytes: file.size,
      });
    } catch (error) {
      setUploadState({
        status: "error",
        message: describe(error, "The file was uploaded but could not be confirmed."),
      });
      return;
    }

    setUploadState({ status: "idle" });
    if (inputRef.current) inputRef.current.value = "";
    onUploaded();
  }

  return (
    <div className="stack stack-3">
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        className="visually-hidden"
        aria-label="Choose a video file to upload"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void handleFile(file);
        }}
      />

      <Button
        variant="primary"
        size="md"
        icon={<Icon name="upload" size={16} />}
        disabled={busy || organizationId === null}
        loading={busy}
        loadingLabel={loadingLabel(uploadState)}
        onClick={() => inputRef.current?.click()}
      >
        Upload video
      </Button>

      {uploadState.status === "uploading" ? (
        <UploadProgress filename={uploadState.filename} progress={uploadState.progress} />
      ) : null}

      {uploadState.status === "error" ? (
        <p className="text-caption" role="alert">
          {uploadState.message}
        </p>
      ) : null}
    </div>
  );
}

function loadingLabel(state: UploadState): string {
  switch (state.status) {
    case "requesting":
      return "Preparing upload";
    case "uploading":
      return "Uploading";
    case "confirming":
      return "Confirming upload";
    default:
      return "Uploading";
  }
}

function describe(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function UploadProgress({ filename, progress }: { filename: string; progress: number | null }) {
  const percent = progress === null ? null : Math.round(progress * 100);

  return (
    <div className="stack stack-2">
      <p className="text-caption">
        Uploading {filename}
        {percent === null ? "" : ` — ${percent}%`}
      </p>
      <div
        className="upload-progress"
        role="progressbar"
        aria-label={`Uploading ${filename}`}
        {...(percent === null
          ? { "aria-valuetext": "Uploading" }
          : { "aria-valuenow": percent, "aria-valuemin": 0, "aria-valuemax": 100 })}
        data-indeterminate={percent === null ? "true" : undefined}
      >
        <span
          className="upload-progress__bar"
          style={percent === null ? undefined : { width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
