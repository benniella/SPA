import { api, type RequestOptions } from "@/lib/api-client";
import { queryString } from "@/services/query";
import type {
  Administrator,
  AuditEvent,
  InvitationAccepted,
  InvitationCreatePayload,
  InvitationCreateResult,
  InvitationResendResult,
  InvitationRevokeResult,
  MfaChallenge,
  MfaChallengeStarted,
  MfaCodeSubmitPayload,
  MfaEnrollmentMaterial,
  MfaRecoveryCodes,
  Page,
  PrivilegeList,
  RoleList,
  RolesUpdatePayload,
} from "@/types/api";

export function currentAdministrator(options?: RequestOptions): Promise<Administrator> {
  return api.get<Administrator>("/admin/me", options);
}

export function listAdministrators(
  params: { limit?: number; offset?: number } = {},
  options?: RequestOptions,
): Promise<Page<Administrator>> {
  return api.get<Page<Administrator>>(`/admin/administrators${queryString(params)}`, options);
}

export function getAdministrator(id: string, options?: RequestOptions): Promise<Administrator> {
  return api.get<Administrator>(`/admin/administrators/${encodeURIComponent(id)}`, options);
}

export function suspendAdministrator(id: string, options?: RequestOptions): Promise<Administrator> {
  return api.post<Administrator>(
    `/admin/administrators/${encodeURIComponent(id)}/suspend`,
    undefined,
    options,
  );
}

export function reactivateAdministrator(
  id: string,
  options?: RequestOptions,
): Promise<Administrator> {
  return api.post<Administrator>(
    `/admin/administrators/${encodeURIComponent(id)}/reactivate`,
    undefined,
    options,
  );
}

export function revokeAdministrator(id: string, options?: RequestOptions): Promise<Administrator> {
  return api.post<Administrator>(
    `/admin/administrators/${encodeURIComponent(id)}/revoke`,
    undefined,
    options,
  );
}

export function listAdministratorRoles(id: string, options?: RequestOptions): Promise<RoleList> {
  return api.get<RoleList>(`/admin/administrators/${encodeURIComponent(id)}/roles`, options);
}

export function setAdministratorRoles(
  id: string,
  payload: RolesUpdatePayload,
  options?: RequestOptions,
): Promise<RoleList> {
  return api.put<RoleList>(
    `/admin/administrators/${encodeURIComponent(id)}/roles`,
    payload,
    options,
  );
}

export function listRoles(options?: RequestOptions): Promise<RoleList> {
  return api.get<RoleList>("/admin/roles", options);
}

export function listPrivileges(options?: RequestOptions): Promise<PrivilegeList> {
  return api.get<PrivilegeList>("/admin/privileges", options);
}

export function createInvitation(
  payload: InvitationCreatePayload,
  options?: RequestOptions,
): Promise<InvitationCreateResult> {
  return api.post<InvitationCreateResult>("/admin/invitations", payload, options);
}

export function resendInvitation(
  invitationId: string,
  options?: RequestOptions,
): Promise<InvitationResendResult> {
  return api.post<InvitationResendResult>(
    `/admin/invitations/${encodeURIComponent(invitationId)}/resend`,
    undefined,
    options,
  );
}

export function revokeInvitation(
  invitationId: string,
  options?: RequestOptions,
): Promise<InvitationRevokeResult> {
  return api.post<InvitationRevokeResult>(
    `/admin/invitations/${encodeURIComponent(invitationId)}/revoke`,
    undefined,
    options,
  );
}

export function acceptInvitation(
  token: string,
  options?: RequestOptions,
): Promise<InvitationAccepted> {
  return api.post<InvitationAccepted>("/admin/invitations/accept", { token }, options);
}

export function beginMfaEnrollment(options?: RequestOptions): Promise<MfaEnrollmentMaterial> {
  return api.post<MfaEnrollmentMaterial>("/admin/mfa/enroll", undefined, options);
}

export function confirmMfaEnrollment(
  payload: MfaCodeSubmitPayload,
  options?: RequestOptions,
): Promise<MfaChallengeStarted> {
  return api.post<MfaChallengeStarted>("/admin/mfa/enroll/confirm", payload, options);
}

export function startMfaChallenge(options?: RequestOptions): Promise<MfaChallenge> {
  return api.post<MfaChallenge>("/admin/mfa/challenge", undefined, options);
}

export function satisfyChallengeWithTotp(
  payload: MfaCodeSubmitPayload,
  options?: RequestOptions,
): Promise<{ status: string }> {
  return api.post<{ status: string }>("/admin/mfa/challenge/totp", payload, options);
}

export function satisfyChallengeWithRecoveryCode(
  payload: MfaCodeSubmitPayload,
  options?: RequestOptions,
): Promise<{ status: string }> {
  return api.post<{ status: string }>("/admin/mfa/challenge/recovery-code", payload, options);
}

export function generateRecoveryCodes(options?: RequestOptions): Promise<MfaRecoveryCodes> {
  return api.post<MfaRecoveryCodes>("/admin/mfa/recovery-codes", undefined, options);
}

export function listAuditEvents(
  params: { limit?: number; offset?: number; event_type?: string } = {},
  options?: RequestOptions,
): Promise<Page<AuditEvent>> {
  return api.get<Page<AuditEvent>>(`/admin/audit-events${queryString(params)}`, options);
}
