import { api, type RequestOptions } from "@/lib/api-client";
import type {
  AuthenticatedUser,
  EmailChangePayload,
  LoginPayload,
  MessageAccepted,
  Page,
  PasswordChangePayload,
  PasswordResetPayload,
  RecoveryCompletePayload,
  RegisterPayload,
  RegistrationAccepted,
  SecurityEventRead,
  SessionSummary,
} from "@/types/api";

export function register(
  payload: RegisterPayload,
  options?: RequestOptions,
): Promise<RegistrationAccepted> {
  return api.post<RegistrationAccepted>("/auth/register", payload, options);
}

export function login(payload: LoginPayload, options?: RequestOptions): Promise<AuthenticatedUser> {
  return api.post<AuthenticatedUser>("/auth/login", payload, options);
}

export function logout(options?: RequestOptions): Promise<MessageAccepted> {
  return api.post<MessageAccepted>("/auth/logout", undefined, options);
}

export function currentUser(options?: RequestOptions): Promise<AuthenticatedUser> {
  return api.get<AuthenticatedUser>("/auth/me", options);
}

export function verifyEmail(token: string, options?: RequestOptions): Promise<AuthenticatedUser> {
  return api.post<AuthenticatedUser>("/auth/verify-email", { token }, options);
}

export function resendVerification(email: string, options?: RequestOptions): Promise<MessageAccepted> {
  return api.post<MessageAccepted>("/auth/resend-verification", { email }, options);
}

export function forgotPassword(email: string, options?: RequestOptions): Promise<MessageAccepted> {
  return api.post<MessageAccepted>("/auth/forgot-password", { email }, options);
}

export function resetPassword(
  payload: PasswordResetPayload,
  options?: RequestOptions,
): Promise<MessageAccepted> {
  return api.post<MessageAccepted>("/auth/reset-password", payload, options);
}

export function changePassword(
  payload: PasswordChangePayload,
  options?: RequestOptions,
): Promise<MessageAccepted> {
  return api.post<MessageAccepted>("/auth/change-password", payload, options);
}

export function requestEmailChange(
  payload: EmailChangePayload,
  options?: RequestOptions,
): Promise<MessageAccepted> {
  return api.post<MessageAccepted>("/account/email/request-change", payload, options);
}

export function verifyEmailChange(
  token: string,
  options?: RequestOptions,
): Promise<MessageAccepted> {
  return api.post<MessageAccepted>("/account/email/verify-change", { token }, options);
}

export function requestPhoneVerification(
  phoneNumber: string,
  options?: RequestOptions,
): Promise<MessageAccepted> {
  return api.post<MessageAccepted>(
    "/account/phone/request-verification",
    { phone_number: phoneNumber },
    options,
  );
}

export function verifyPhone(code: string, options?: RequestOptions): Promise<MessageAccepted> {
  return api.post<MessageAccepted>("/account/phone/verify", { code }, options);
}

export function removePhone(options?: RequestOptions): Promise<void> {
  return api.delete<void>("/account/phone", options);
}

export function listSessions(options?: RequestOptions): Promise<Page<SessionSummary>> {
  return api.get<Page<SessionSummary>>("/account/sessions", options);
}

export function revokeSession(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/account/sessions/${encodeURIComponent(id)}`, options);
}

export function revokeAllSessions(options?: RequestOptions): Promise<MessageAccepted> {
  return api.post<MessageAccepted>("/account/sessions/revoke-all", undefined, options);
}

export function listSecurityEvents(options?: RequestOptions): Promise<Page<SecurityEventRead>> {
  return api.get<Page<SecurityEventRead>>("/account/security-events", options);
}

export function startRecovery(email: string, options?: RequestOptions): Promise<MessageAccepted> {
  return api.post<MessageAccepted>("/account/recovery/start", { email }, options);
}

export function completeRecovery(
  payload: RecoveryCompletePayload,
  options?: RequestOptions,
): Promise<MessageAccepted> {
  return api.post<MessageAccepted>("/account/recovery/complete", payload, options);
}