import type { AnalysisRunStatus, ProcessingJobStatus, VideoStatus } from "@/types/api";

export type Sport = "football" | "basketball" | "rugby" | "other";

export type PeriodLabel = "first_half" | "second_half" | "full_match" | "extra_time";

export const videoStatusLabels: Record<VideoStatus, string> = {
  pending: "Awaiting upload",
  uploading: "Uploading",
  uploaded: "Uploaded",
  stored: "Uploaded",
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
};

export const processingStatusLabels: Record<ProcessingJobStatus, string> = {
  queued: "Queued",
  running: "Processing",
  completed: "Processed",
  failed: "Failed",
};

export function isTerminalJobStatus(status: ProcessingJobStatus): boolean {
  return status === "completed" || status === "failed";
}

export const analysisStatusLabels: Record<AnalysisRunStatus, string> = {
  pending: "Pending",
  queued: "Queued",
  running: "Analysing",
  succeeded: "Complete",
  partially_succeeded: "Partial",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function isTerminalStatus(status: AnalysisRunStatus): boolean {
  return (
    status === "succeeded" ||
    status === "partially_succeeded" ||
    status === "failed" ||
    status === "cancelled"
  );
}

export function hasUsableResults(status: AnalysisRunStatus): boolean {
  return status === "succeeded" || status === "partially_succeeded";
}
