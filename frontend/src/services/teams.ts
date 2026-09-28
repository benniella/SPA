import { api, type RequestOptions } from "@/lib/api-client";
import { queryString } from "@/services/query";
import type { Page, Team, TeamCreate } from "@/types/api";

export function listTeams(
  organizationId: string,
  params: { limit?: number; offset?: number } = {},
  options?: RequestOptions,
): Promise<Page<Team>> {
  return api.get<Page<Team>>(
    `/teams${queryString({ organization_id: organizationId, ...params })}`,
    options,
  );
}

export function getTeam(
  id: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<Team> {
  return api.get<Team>(
    `/teams/${encodeURIComponent(id)}${queryString({ organization_id: organizationId })}`,
    options,
  );
}

export function createTeam(payload: TeamCreate, options?: RequestOptions): Promise<Team> {
  return api.post<Team>("/teams", payload, options);
}
