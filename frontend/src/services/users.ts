import { api, type RequestOptions } from "@/lib/api-client";
import { queryString } from "@/services/query";
import type { Page, User, UserCreate } from "@/types/api";

export function listUsers(
  params: { limit?: number; offset?: number } = {},
  options?: RequestOptions,
): Promise<Page<User>> {
  return api.get<Page<User>>(`/users${queryString(params)}`, options);
}

export function getUser(id: string, options?: RequestOptions): Promise<User> {
  return api.get<User>(`/users/${encodeURIComponent(id)}`, options);
}

export function createUser(payload: UserCreate, options?: RequestOptions): Promise<User> {
  return api.post<User>("/users", payload, options);
}
