import { api, type RequestOptions } from "@/lib/api-client";
import { queryString } from "@/services/query";
import type { Match, MatchCreate, Page } from "@/types/api";

export function listMatches(
  organizationId: string,
  params: { limit?: number; offset?: number } = {},
  options?: RequestOptions,
): Promise<Page<Match>> {
  return api.get<Page<Match>>(
    `/matches${queryString({ organization_id: organizationId, ...params })}`,
    options,
  );
}

export function getMatch(
  id: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<Match> {
  return api.get<Match>(
    `/matches/${encodeURIComponent(id)}${queryString({ organization_id: organizationId })}`,
    options,
  );
}

export function createMatch(payload: MatchCreate, options?: RequestOptions): Promise<Match> {
  return api.post<Match>("/matches", payload, options);
}
