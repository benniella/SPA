import { describe, expect, it } from "vitest";

import { resolveAdminAccess } from "@/features/admin/access";
import { ApiError, NetworkError } from "@/lib/api-errors";
import type { Administrator, AuthenticatedUser } from "@/types/api";

const USER: AuthenticatedUser = {
  id: "user-1",
  email: "person@example.com",
  display_name: "Person",
  account_status: "active",
  email_verified: true,
  phone_verified: false,
  phone_number: null,
  created_at: "2025-01-01T00:00:00Z",
  last_login_at: null,
  organizations: [],
};

function administrator(overrides: Partial<Administrator> = {}): Administrator {
  return {
    id: "admin-1",
    user_id: USER.id,
    email: USER.email,
    status: "active",
    roles: [],
    privileges: [],
    mfa_enrolled: true,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("resolveAdminAccess", () => {
  it("is anonymous when there is no user and no error", () => {
    expect(resolveAdminAccess({ user: null, administrator: null, error: null }).state).toBe(
      "anonymous",
    );
  });

  it("treats a 403 as an authenticated non-administrator", () => {
    const access = resolveAdminAccess({
      user: USER,
      administrator: null,
      error: new ApiError(403, "permission_denied", "Not an administrator."),
    });
    expect(access.state).toBe("authenticated-non-admin");
  });

  it("treats a 401 with a resolved user as a required second factor", () => {
    const access = resolveAdminAccess({
      user: USER,
      administrator: null,
      error: new ApiError(401, "authentication_required", "A second factor is required."),
    });
    expect(access.state).toBe("admin-mfa-required");
  });

  it("surfaces a genuine failure as an error state", () => {
    const access = resolveAdminAccess({
      user: USER,
      administrator: null,
      error: new NetworkError("Could not reach the SPA API."),
    });
    expect(access.state).toBe("error");
  });

  it("does not equate an administrator with an active one", () => {
    const access = resolveAdminAccess({
      user: USER,
      administrator: administrator({ status: "invited", mfa_enrolled: false }),
      error: null,
    });
    expect(access.state).toBe("admin-invited");
  });

  it("routes an enrolled-but-unassured administrator into the challenge", () => {
    const access = resolveAdminAccess({
      user: USER,
      administrator: administrator({ status: "invited", mfa_enrolled: true }),
      error: null,
    });
    expect(access.state).toBe("admin-mfa-required");
  });

  it("marks an active administrator with an enrolled factor as active", () => {
    const access = resolveAdminAccess({
      user: USER,
      administrator: administrator(),
      error: null,
    });
    expect(access.state).toBe("admin-active");
  });

  it("reports suspended and revoked separately", () => {
    const suspended = resolveAdminAccess({
      user: USER,
      administrator: administrator({ status: "suspended" }),
      error: null,
    });
    const revoked = resolveAdminAccess({
      user: USER,
      administrator: administrator({ status: "revoked" }),
      error: null,
    });

    expect(suspended.state).toBe("admin-suspended");
    expect(revoked.state).toBe("admin-revoked");
  });
});
