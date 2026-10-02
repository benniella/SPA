import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  acceptInvitation,
  beginMfaEnrollment,
  confirmMfaEnrollment,
  createInvitation,
  currentAdministrator,
  generateRecoveryCodes,
  getAdministrator,
  listAdministrators,
  listAdministratorRoles,
  listAuditEvents,
  listPrivileges,
  listRoles,
  reactivateAdministrator,
  resendInvitation,
  revokeAdministrator,
  revokeInvitation,
  setAdministratorRoles,
  satisfyChallengeWithRecoveryCode,
  satisfyChallengeWithTotp,
  startMfaChallenge,
  suspendAdministrator,
} from "@/services/admin";

function mockFetch(json: unknown = {}) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    headers: new Headers(),
    json: async () => json,
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function callOf(fetchMock: ReturnType<typeof vi.fn>, call = 0): [string, RequestInit] {
  return fetchMock.mock.calls[call] as [string, RequestInit];
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  vi.stubEnv("NEXT_PUBLIC_API_VERSION_PREFIX", "/api/v1");
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("administrator endpoints", () => {
  it("reads the administrator behind this session", async () => {
    const fetchMock = mockFetch({ status: "active" });
    await currentAdministrator();
    expect(callOf(fetchMock)[0]).toBe("http://localhost:8000/api/v1/admin/me");
  });

  it("paginates the administrator list", async () => {
    const fetchMock = mockFetch({ items: [], meta: { limit: 200, offset: 0, count: 0 } });
    await listAdministrators({ limit: 200, offset: 50 });

    const url = callOf(fetchMock)[0];
    expect(url).toContain("/api/v1/admin/administrators");
    expect(url).toContain("limit=200");
    expect(url).toContain("offset=50");
  });

  it("encodes the administrator id on the detail read", async () => {
    const fetchMock = mockFetch({});
    await getAdministrator("admin/1");
    expect(callOf(fetchMock)[0]).toContain("/admin/administrators/admin%2F1");
  });

  it("posts lifecycle transitions without a body", async () => {
    const fetchMock = mockFetch({});

    await suspendAdministrator("a1");
    await reactivateAdministrator("a1");
    await revokeAdministrator("a1");

    expect(callOf(fetchMock, 0)[0]).toContain("/admin/administrators/a1/suspend");
    expect(callOf(fetchMock, 1)[0]).toContain("/admin/administrators/a1/reactivate");
    expect(callOf(fetchMock, 2)[0]).toContain("/admin/administrators/a1/revoke");
    expect(callOf(fetchMock, 0)[1].method).toBe("POST");
  });
});

describe("role endpoints", () => {
  it("reads roles, privileges and an administrator's held roles", async () => {
    const fetchMock = mockFetch({ items: [] });

    await listRoles();
    await listPrivileges();
    await listAdministratorRoles("a1");

    expect(callOf(fetchMock, 0)[0]).toBe("http://localhost:8000/api/v1/admin/roles");
    expect(callOf(fetchMock, 1)[0]).toBe("http://localhost:8000/api/v1/admin/privileges");
    expect(callOf(fetchMock, 2)[0]).toContain("/admin/administrators/a1/roles");
  });

  it("replaces the role set with a PUT of the complete list", async () => {
    const fetchMock = mockFetch({ items: ["support_admin"] });
    await setAdministratorRoles("a1", { roles: ["support_admin"] });

    const [url, init] = callOf(fetchMock);
    expect(url).toContain("/admin/administrators/a1/roles");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({ roles: ["support_admin"] });
  });
});

describe("invitation endpoints", () => {
  it("creates an invitation with the invitee and role", async () => {
    const fetchMock = mockFetch({ invitation_id: "i1", status: "pending" });
    await createInvitation({ email: "new@example.com", role: "support_admin" });

    const [url, init] = callOf(fetchMock);
    expect(url).toBe("http://localhost:8000/api/v1/admin/invitations");
    expect(JSON.parse(init.body as string)).toEqual({
      email: "new@example.com",
      role: "support_admin",
    });
  });

  it("resends and revokes by invitation id", async () => {
    const fetchMock = mockFetch({});
    await resendInvitation("i1");
    await revokeInvitation("i1");

    expect(callOf(fetchMock, 0)[0]).toContain("/admin/invitations/i1/resend");
    expect(callOf(fetchMock, 1)[0]).toContain("/admin/invitations/i1/revoke");
  });

  it("accepts an invitation with the raw token in the body only", async () => {
    const fetchMock = mockFetch({ administrator_id: "a1", status: "invited" });
    await acceptInvitation("token-value");

    const [url, init] = callOf(fetchMock);
    expect(url).toBe("http://localhost:8000/api/v1/admin/invitations/accept");
    expect(JSON.parse(init.body as string)).toEqual({ token: "token-value" });
    expect(url).not.toContain("token-value");
  });
});

describe("MFA endpoints", () => {
  it("begins enrolment and confirms with a code", async () => {
    const fetchMock = mockFetch({});

    await beginMfaEnrollment();
    await confirmMfaEnrollment({ code: "123456" });
    await startMfaChallenge();

    expect(callOf(fetchMock, 0)[0]).toContain("/admin/mfa/enroll");
    expect(callOf(fetchMock, 1)[0]).toContain("/admin/mfa/enroll/confirm");
    expect(callOf(fetchMock, 2)[0]).toContain("/admin/mfa/challenge");
  });

  it("satisfies the challenge by TOTP or recovery code", async () => {
    const fetchMock = mockFetch({ status: "verified" });

    await satisfyChallengeWithTotp({ code: "123456" });
    await satisfyChallengeWithRecoveryCode({ code: "ABCDE-FGHIJ" });

    expect(callOf(fetchMock, 0)[0]).toContain("/admin/mfa/challenge/totp");
    expect(callOf(fetchMock, 1)[0]).toContain("/admin/mfa/challenge/recovery-code");
  });

  it("generates recovery codes from their own endpoint", async () => {
    const fetchMock = mockFetch({ codes: ["AAAAA-BBBBB"] });
    await generateRecoveryCodes();
    expect(callOf(fetchMock)[0]).toContain("/admin/mfa/recovery-codes");
  });
});

describe("audit endpoint", () => {
  it("passes pagination and the optional event type filter", async () => {
    const fetchMock = mockFetch({ items: [], meta: { limit: 25, offset: 25, count: 0 } });
    await listAuditEvents({ limit: 25, offset: 25, event_type: "ADMIN_SUSPENDED" });

    const url = callOf(fetchMock)[0];
    expect(url).toContain("/api/v1/admin/audit-events");
    expect(url).toContain("offset=25");
    expect(url).toContain("event_type=ADMIN_SUSPENDED");
  });

  it("omits an unset event type rather than sending an empty filter", async () => {
    const fetchMock = mockFetch({ items: [], meta: { limit: 25, offset: 0, count: 0 } });
    await listAuditEvents({ limit: 25, offset: 0, event_type: "" });

    expect(callOf(fetchMock)[0]).not.toContain("event_type");
  });
});
