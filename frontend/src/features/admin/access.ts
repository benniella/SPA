import { ApiError, NetworkError } from "@/lib/api-errors";
import type { Administrator, AuthenticatedUser } from "@/types/api";

/* The backend's administrator lifecycle vocabulary ('app/domain/admin/entities.py').
   'invited' is a real, reachable state: accepting an invitation creates an
   administrator record without granting access. The frontend must not assume
   administrator implies active. */
export type AdminStatus = "invited" | "active" | "suspended" | "revoked";

export const ADMIN_STATUSES: readonly AdminStatus[] = ["invited", "active", "suspended", "revoked"];

export function isAdminStatus(value: string): value is AdminStatus {
  return (ADMIN_STATUSES as readonly string[]).includes(value);
}

export type AdminAccessState =
  | { readonly state: "anonymous" }
  | { readonly state: "authenticated-non-admin" }
  | { readonly state: "admin-mfa-required"; readonly status: AdminStatus }
  | { readonly state: "admin-invited"; readonly admin: Administrator }
  | { readonly state: "admin-active"; readonly admin: Administrator }
  | { readonly state: "admin-suspended"; readonly admin: Administrator }
  | { readonly state: "admin-revoked"; readonly admin: Administrator }
  | { readonly state: "error"; readonly error: Error };

export type AdminResolution =
  | { readonly status: "loading" }
  | { readonly status: "resolved"; readonly access: AdminAccessState };

export interface AdminAccessSubject {
  readonly user: AuthenticatedUser | null;
  readonly administrator: Administrator | null;
  readonly error: Error | null;
}

/* A 403 means "authenticated, but not an administrator"; a 401 from an admin
   endpoint means the administrator is not MFA-assured yet. Both are answers, not
   failures, so they resolve to a state rather than surfacing as an error. */
export function resolveAdminAccess({
  user,
  administrator,
  error,
}: AdminAccessSubject): AdminAccessState {
  if (error instanceof ApiError && error.status === 403) {
    return { state: "authenticated-non-admin" };
  }

  if (error instanceof ApiError && error.status === 401) {
    if (!user) return { state: "anonymous" };
    return { state: "admin-mfa-required", status: "invited" };
  }

  if (error) {
    return { state: "error", error };
  }

  if (!user) {
    return { state: "anonymous" };
  }

  if (!administrator) {
    return { state: "authenticated-non-admin" };
  }

  const status = administrator.status;

  if (status === "invited") {
    return administrator.mfa_enrolled
      ? { state: "admin-mfa-required", status }
      : { state: "admin-invited", admin: administrator };
  }

  if (status === "active") {
    return administrator.mfa_enrolled
      ? { state: "admin-active", admin: administrator }
      : { state: "admin-mfa-required", status };
  }

  if (status === "suspended") {
    return { state: "admin-suspended", admin: administrator };
  }

  if (status === "revoked") {
    return { state: "admin-revoked", admin: administrator };
  }

  return { state: "admin-mfa-required", status: "invited" };
}

export function adminAccessDenied(error: Error): boolean {
  return (
    (error instanceof ApiError && (error.status === 401 || error.status === 403)) ||
    error instanceof NetworkError
  );
}
