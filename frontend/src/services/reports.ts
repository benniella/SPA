import { api, type RequestOptions } from "@/lib/api-client";
import { queryString } from "@/services/query";
import type { Page, Report, ReportDetail } from "@/types/api";

export function listReports(
  organizationId: string,
  params: { limit?: number; offset?: number } = {},
  options?: RequestOptions,
): Promise<Page<Report>> {
  return api.get<Page<Report>>(
    `/reports${queryString({ organization_id: organizationId, ...params })}`,
    options,
  );
}

export function getReport(
  id: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<ReportDetail> {
  return api.get<ReportDetail>(
    `/reports/${encodeURIComponent(id)}${queryString({ organization_id: organizationId })}`,
    options,
  );
}

export function createRunReport(
  runId: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<Report> {
  return api.post<Report>(
    `/analysis-runs/${encodeURIComponent(runId)}/reports${queryString({
      organization_id: organizationId,
    })}`,
    undefined,
    options,
  );
}
