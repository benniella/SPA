import { api, type RequestOptions } from "@/lib/api-client";
import { queryString } from "@/services/query";
import type { ProcessingJob, VideoProcessing } from "@/types/api";

export function requestVideoProcessing(
  videoId: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<ProcessingJob> {
  return api.post<ProcessingJob>(
    `/videos/${encodeURIComponent(videoId)}/process`,
    { organization_id: organizationId },
    options,
  );
}

export function getProcessingJob(
  id: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<ProcessingJob> {
  return api.get<ProcessingJob>(
    `/processing-jobs/${encodeURIComponent(id)}${queryString({ organization_id: organizationId })}`,
    options,
  );
}

export function getVideoProcessing(
  videoId: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<VideoProcessing> {
  return api.get<VideoProcessing>(
    `/videos/${encodeURIComponent(videoId)}/processing${queryString({
      organization_id: organizationId,
    })}`,
    options,
  );
}

export function listVideoProcessingJobs(
  videoId: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<ProcessingJob[]> {
  return api.get<ProcessingJob[]>(
    `/videos/${encodeURIComponent(videoId)}/processing/jobs${queryString({
      organization_id: organizationId,
    })}`,
    options,
  );
}
