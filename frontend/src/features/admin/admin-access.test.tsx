import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AdminSessionProvider } from "@/features/admin/session";
import { RequireAdmin } from "@/features/admin";
import { InvitationAcceptance } from "@/features/admin";
import { SessionProvider } from "@/features/auth/session";
import type { Administrator, AuthenticatedUser } from "@/types/api";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/administrators",
  useRouter: () => ({ replace, push: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const ACCOUNT: AuthenticatedUser = {
  id: "user-1",
  email: "admin@example.com",
  display_name: "Admin",
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
    user_id: ACCOUNT.id,
    email: ACCOUNT.email,
    status: "active",
    roles: ["superadmin"],
    privileges: ["admins.read", "admins.manage"],
    mfa_enrolled: true,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
    ...overrides,
  };
}

interface StubOptions {
  readonly admin?: Administrator | null;
  readonly adminStatus?: number;
  readonly adminError?: { code: string; message: string };
  readonly authenticated?: boolean;
  readonly routes?: Record<string, unknown>;
  readonly routeStatus?: Record<string, number>;
}

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers(),
    json: async () => payload,
  } as Response;
}

function stubApi(options: StubOptions = {}) {
  const routes = options.routes ?? {};
  const statuses = options.routeStatus ?? {};

  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.includes("/auth/me")) {
      return options.authenticated === false
        ? jsonResponse({ error: { code: "authentication_required", message: "Sign in." } }, 401)
        : jsonResponse(ACCOUNT);
    }

    if (url.includes("/admin/me")) {
      if (options.adminError)
        return jsonResponse({ error: options.adminError }, options.adminStatus ?? 403);
      if (options.admin === null)
        return jsonResponse({ error: { code: "not_found", message: "None." } }, 404);
      return jsonResponse(options.admin ?? administrator());
    }

    for (const [path, payload] of Object.entries(routes)) {
      if (url.includes(path)) return jsonResponse(payload, statuses[path] ?? 200);
    }

    return jsonResponse({ error: { code: "not_found", message: `No stub for ${url}.` } }, 404);
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function withAdminBoundary(children: React.ReactNode) {
  return render(
    <SessionProvider>
      <AdminSessionProvider>
        <RequireAdmin from="/admin/administrators">{children}</RequireAdmin>
      </AdminSessionProvider>
    </SessionProvider>,
  );
}

async function settled(assertion: () => void) {
  await waitFor(assertion, { timeout: 3000 });
}

beforeEach(() => {
  replace.mockClear();
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
});

describe("admin route boundary", () => {
  it("redirects an unauthenticated visitor into the existing sign-in flow", async () => {
    stubApi({ authenticated: false });

    withAdminBoundary(<p>Administrative content</p>);

    await settled(() =>
      expect(replace).toHaveBeenCalledWith("/sign-in?from=%2Fadmin%2Fadministrators"),
    );
    expect(screen.queryByText("Administrative content")).not.toBeInTheDocument();
  });

  it("does not show administrative UI to an authenticated non-administrator", async () => {
    stubApi({
      adminStatus: 403,
      adminError: { code: "permission_denied", message: "Not an administrator." },
    });

    withAdminBoundary(<p>Administrative content</p>);

    await settled(() =>
      expect(screen.getByText(/does not have administrative access/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText("Administrative content")).not.toBeInTheDocument();
  });

  it("renders the administrative surface for an active administrator", async () => {
    stubApi({ admin: administrator() });

    withAdminBoundary(<p>Administrative content</p>);

    await settled(() => expect(screen.getByText("Administrative content")).toBeInTheDocument());
    expect(replace).not.toHaveBeenCalled();
  });

  it("directs an invited administrator into the MFA enrollment flow", async () => {
    stubApi({ admin: administrator({ status: "invited", mfa_enrolled: false }) });

    withAdminBoundary(<p>Administrative content</p>);

    await settled(() => expect(screen.getByText(/Continue security setup/i)).toBeInTheDocument());
    expect(screen.queryByText("Administrative content")).not.toBeInTheDocument();
  });

  it("directs an enrolled but unassured administrator into the MFA challenge", async () => {
    stubApi({
      adminStatus: 401,
      adminError: { code: "authentication_required", message: "A second factor is required." },
    });

    withAdminBoundary(<p>Administrative content</p>);

    await settled(() => expect(screen.getByText(/second factor is required/i)).toBeInTheDocument());
  });

  it("gives a suspended administrator an explicit access state", async () => {
    stubApi({ admin: administrator({ status: "suspended" }) });

    withAdminBoundary(<p>Administrative content</p>);

    await settled(() =>
      expect(screen.getByText(/Administrative access is unavailable/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/suspended/i)).toBeInTheDocument();
  });

  it("gives a revoked administrator an explicit access state", async () => {
    stubApi({ admin: administrator({ status: "revoked" }) });

    withAdminBoundary(<p>Administrative content</p>);

    await settled(() => expect(screen.getByText(/has been revoked/i)).toBeInTheDocument());
  });
});

describe("invitation acceptance", () => {
  it("accepts a valid invitation and does not claim activation", async () => {
    const fetchMock = stubApi({
      authenticated: true,
      routes: { "/admin/invitations/accept": { administrator_id: "admin-1", status: "invited" } },
    });

    render(
      <SessionProvider>
        <InvitationAcceptance token="valid-token" />
      </SessionProvider>,
    );

    await settled(() => expect(screen.getByText(/Invitation accepted/i)).toBeInTheDocument());
    expect(screen.getByText(/does not grant access yet/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Continue to security setup/i })).toHaveAttribute(
      "href",
      "/admin/security",
    );

    const acceptCall = fetchMock.mock.calls.find((call) => String(call[0]).includes("/accept"));
    expect(acceptCall).toBeTruthy();
  });

  it("explains an unknown or invalid invitation", async () => {
    stubApi({
      authenticated: true,
      routes: {
        "/admin/invitations/accept": { error: { code: "not_found", message: "Not valid." } },
      },
      routeStatus: { "/admin/invitations/accept": 404 },
    });

    render(
      <SessionProvider>
        <InvitationAcceptance token="unknown-token" />
      </SessionProvider>,
    );

    await settled(() => expect(screen.getByText(/not valid/i)).toBeInTheDocument());
  });

  it("explains an expired, revoked or already-used invitation", async () => {
    stubApi({
      authenticated: true,
      routes: {
        "/admin/invitations/accept": {
          error: { code: "conflict", message: "This invitation is no longer valid." },
        },
      },
      routeStatus: { "/admin/invitations/accept": 409 },
    });

    render(
      <SessionProvider>
        <InvitationAcceptance token="spent-token" />
      </SessionProvider>,
    );

    await settled(() => expect(screen.getByText(/no longer usable/i)).toBeInTheDocument());
  });

  it("reports a malformed invitation link", async () => {
    stubApi({ authenticated: true });

    render(
      <SessionProvider>
        <InvitationAcceptance token="" />
      </SessionProvider>,
    );

    await settled(() => expect(screen.getByText(/link is incomplete/i)).toBeInTheDocument());
  });

  it("handles a network failure distinctly", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/auth/me")) return jsonResponse(ACCOUNT);
        throw new TypeError("Failed to fetch");
      }),
    );

    render(
      <SessionProvider>
        <InvitationAcceptance token="valid-token" />
      </SessionProvider>,
    );

    await settled(() => expect(screen.getByText(/Could not reach SPA/i)).toBeInTheDocument());
  });

  it("never writes the invitation token to browser storage", async () => {
    stubApi({
      authenticated: true,
      routes: { "/admin/invitations/accept": { administrator_id: "admin-1", status: "invited" } },
    });

    render(
      <SessionProvider>
        <InvitationAcceptance token="secret-invitation-token" />
      </SessionProvider>,
    );

    await settled(() => expect(screen.getByText(/Invitation accepted/i)).toBeInTheDocument());

    const stored = JSON.stringify(window.localStorage).concat(document.cookie);
    expect(stored).not.toContain("secret-invitation-token");
  });
});
