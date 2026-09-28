import { api, type RequestOptions } from "@/lib/api-client";
import { queryString } from "@/services/query";
import type {
  AnalysisMetrics,
  AnalysisRun,
  MetricsCalculation,
  Page,
  RunVisualization,
} from "@/types/api";

export function listAnalysisRuns(
  videoId: string,
  params: { limit?: number; offset?: number } = {},
  options?: RequestOptions,
): Promise<Page<AnalysisRun>> {
  return api.get<Page<AnalysisRun>>(
    `/analysis-runs${queryString({ video_id: videoId, ...params })}`,
    options,
  );
}

export function getAnalysisRun(
  id: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<AnalysisRun> {
  return api.get<AnalysisRun>(
    `/analysis-runs/${encodeURIComponent(id)}${queryString({ organization_id: organizationId })}`,
    options,
  );
}

export function cancelAnalysisRun(
  id: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<AnalysisRun> {
  return api.post<AnalysisRun>(
    `/analysis-runs/${encodeURIComponent(id)}/cancel${queryString({
      organization_id: organizationId,
    })}`,
    undefined,
    options,
  );
}

export function calculateAnalysisMetrics(
  id: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<MetricsCalculation> {
  return api.post<MetricsCalculation>(
    `/analysis-runs/${encodeURIComponent(id)}/metrics${queryString({
      organization_id: organizationId,
    })}`,
    undefined,
    options,
  );
}

export function getAnalysisMetrics(
  id: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<AnalysisMetrics> {
  return api.get<AnalysisMetrics>(
    `/analysis-runs/${encodeURIComponent(id)}/metrics${queryString({
      organization_id: organizationId,
    })}`,
    options,
  );
}

export function getRunVisualization(
  id: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<RunVisualization> {
  return api.get<RunVisualization>(
    `/analysis-runs/${encodeURIComponent(id)}/visualization${queryString({
      organization_id: organizationId,
    })}`,
    options,
  );
}
