import { api, type RequestOptions } from "@/lib/api-client";
import { queryString } from "@/services/query";
import type { Organization, OrganizationCreate, Page } from "@/types/api";

export function listOrganizations(
  params: { limit?: number; offset?: number } = {},
  options?: RequestOptions,
): Promise<Page<Organization>> {
  return api.get<Page<Organization>>(`/organizations${queryString(params)}`, options);
}

export function getOrganization(id: string, options?: RequestOptions): Promise<Organization> {
  return api.get<Organization>(`/organizations/${encodeURIComponent(id)}`, options);
}

export function createOrganization(
  payload: OrganizationCreate,
  options?: RequestOptions,
): Promise<Organization> {
  return api.post<Organization>("/organizations", payload, options);
}
