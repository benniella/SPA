import { api, type RequestOptions } from "@/lib/api-client";
import { queryString } from "@/services/query";
import type {
  Page,
  Video,
  VideoCompleteUploadRequest,
  VideoUploadRequest,
  VideoUploadTicket,
} from "@/types/api";

export function listVideos(
  organizationId: string,
  params: { limit?: number; offset?: number } = {},
  options?: RequestOptions,
): Promise<Page<Video>> {
  return api.get<Page<Video>>(
    `/videos${queryString({ organization_id: organizationId, ...params })}`,
    options,
  );
}

export function getVideo(
  id: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<Video> {
  return api.get<Video>(
    `/videos/${encodeURIComponent(id)}${queryString({ organization_id: organizationId })}`,
    options,
  );
}

export function requestVideoUpload(
  payload: VideoUploadRequest,
  options?: RequestOptions,
): Promise<VideoUploadTicket> {
  return api.post<VideoUploadTicket>("/videos", payload, options);
}

export function completeVideoUpload(
  id: string,
  payload: VideoCompleteUploadRequest,
  options?: RequestOptions,
): Promise<Video> {
  return api.post<Video>("/videos/" + encodeURIComponent(id) + "/complete", payload, options);
}

export function deleteVideo(
  id: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<void> {
  return api.delete<void>(
    "/videos/" + encodeURIComponent(id) + queryString({ organization_id: organizationId }),
    options,
  );
}

export function uploadToStorage(
  url: string,
  file: File,
  options: { onProgress?: (fraction: number | null) => void; signal?: AbortSignal } = {},
): Promise<void> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", url);
    request.setRequestHeader("Content-Type", file.type || "application/octet-stream");

    request.upload.addEventListener("progress", (event) => {
      options.onProgress?.(event.lengthComputable ? event.loaded / event.total : null);
    });

    request.addEventListener("load", () => {
      if (request.status >= 200 && request.status < 300) resolve();
      else reject(new Error("Storage rejected the upload (HTTP " + request.status + ")."));
    });
    request.addEventListener("error", () => reject(new Error("The upload to storage failed.")));
    request.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));

    options.signal?.addEventListener("abort", () => request.abort(), { once: true });
    request.send(file);
  });
}
