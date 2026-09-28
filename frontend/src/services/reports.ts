import { api, type RequestOptions } from "@/lib/api-client";
import { queryString } from "@/services/query";
import type { Page, Report } from "@/types/api";

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
): Promise<Report> {
  return api.get<Report>(
    `/reports/${encodeURIComponent(id)}${queryString({ organization_id: organizationId })}`,
    options,
  );
}
