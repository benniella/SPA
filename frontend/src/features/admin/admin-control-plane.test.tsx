import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuditLog, InvitationList } from "@/features/admin";

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers(),
    json: async () => payload,
  } as Response;
}

interface RouteReply {
  readonly payload: unknown;
  readonly status?: number;
}

function stub(routes: Record<string, RouteReply>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    const path = new URL(url).pathname;
    for (const [route, reply] of Object.entries(routes)) {
      const [routeMethod, routePath] = route.split(" ");
      if (method === routeMethod && path.endsWith(routePath ?? "")) {
        return jsonResponse(reply.payload, reply.status ?? 200);
      }
    }
    return jsonResponse(
      { error: { code: "not_found", message: `No stub for ${method} ${url}` } },
      404,
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function invitation(overrides: Record<string, unknown> = {}) {
  return {
    id: "inv-1",
    email: "invitee@example.com",
    role: "support_admin",
    status: "outstanding",
    invited_by: "admin-1",
    expires_at: "2025-04-01T00:00:00Z",
    accepted_at: null,
    revoked_at: null,
    created_at: "2025-03-25T00:00:00Z",
    ...overrides,
  };
}

function auditEvent(overrides: Record<string, unknown> = {}) {
  return {
    id: "e1",
    actor_id: "actor-1",
    event_type: "ADMIN_SUSPENDED",
    metadata: { from: "active", to: "suspended" },
    created_at: "2025-03-04T10:00:00Z",
    ...overrides,
  };
}

describe("invitation list", () => {
  it("renders invitations with their status and role", async () => {
    stub({
      "GET /admin/invitations": {
        payload: {
          items: [
            invitation(),
            invitation({ id: "inv-2", email: "second@example.com", status: "revoked" }),
          ],
          meta: { limit: 25, offset: 0, count: 2 },
        },
      },
    });

    render(<InvitationList />);

    await waitFor(() => expect(screen.getByText("invitee@example.com")).toBeInTheDocument());
    expect(screen.getByText("revoked")).toBeInTheDocument();
    expect(screen.getAllByText("support_admin").length).toBeGreaterThan(0);
  });

  it("shows the empty state when no invitations match", async () => {
    stub({
      "GET /admin/invitations": {
        payload: { items: [], meta: { limit: 25, offset: 0, count: 0 } },
      },
    });

    render(<InvitationList />);

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "No invitations" })).toBeInTheDocument(),
    );
  });

  it("surfaces an authorization failure instead of hiding it", async () => {
    stub({
      "GET /admin/invitations": {
        payload: { error: { code: "permission_denied", message: "Nope." } },
        status: 403,
      },
    });

    render(<InvitationList />);

    await waitFor(() =>
      expect(screen.getByRole("region", { name: /went wrong/i })).toBeInTheDocument(),
    );
  });

  it("requests the next page with the current filters", async () => {
    const fetchMock = stub({
      "GET /admin/invitations": {
        payload: {
          items: Array.from({ length: 25 }, (_, index) =>
            invitation({ id: `inv-${index}`, email: `invitee${index}@example.com` }),
          ),
          meta: { limit: 25, offset: 0, count: 60 },
        },
      },
    });

    render(<InvitationList />);
    await waitFor(() => expect(screen.getByText("invitee0@example.com")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("offset=25"))).toBe(true),
    );
  });

  it("sends the status filter to the server", async () => {
    const fetchMock = stub({
      "GET /admin/invitations": {
        payload: { items: [invitation()], meta: { limit: 25, offset: 0, count: 1 } },
      },
    });

    render(<InvitationList />);
    await waitFor(() => expect(screen.getByText("invitee@example.com")).toBeInTheDocument());

    await userEvent.selectOptions(screen.getByLabelText("Status"), "revoked");

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("status=revoked"))).toBe(
        true,
      ),
    );
  });

  it("does not offer resend or revoke for an invitation that is no longer outstanding", async () => {
    stub({
      "GET /admin/invitations": {
        payload: { items: [invitation({ status: "revoked" })], meta: { limit: 25, offset: 0, count: 1 } },
      },
    });

    render(<InvitationList />);
    await waitFor(() => expect(screen.getByText("invitee@example.com")).toBeInTheDocument());

    expect(screen.queryByRole("button", { name: "Resend" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Revoke" })).not.toBeInTheDocument();
  });

  it("revokes an outstanding invitation", async () => {
    const fetchMock = stub({
      "GET /admin/invitations": {
        payload: { items: [invitation()], meta: { limit: 25, offset: 0, count: 1 } },
      },
      "POST /admin/invitations/inv-1/revoke": {
        payload: { invitation_id: "inv-1", status: "revoked" },
      },
    });

    render(<InvitationList />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Revoke" })).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Revoke" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/revoke"))).toBe(true),
    );
  });
});

describe("audit filters", () => {
  it("sends actor and date range filters to the server", async () => {
    const fetchMock = stub({
      "GET /admin/audit-events": {
        payload: { items: [auditEvent()], meta: { limit: 25, offset: 0, count: 1 } },
      },
    });

    render(<AuditLog />);
    await waitFor(() => expect(screen.getByText("ADMIN_SUSPENDED")).toBeInTheDocument());

    await userEvent.type(screen.getByLabelText("Actor id"), "actor-9");
    await userEvent.type(screen.getByLabelText("From"), "2025-03-01");

    await userEvent.click(screen.getByRole("button", { name: "Filter" }));

    await waitFor(() => {
      const requested = fetchMock.mock.calls.map(([url]) => String(url));
      expect(requested.some((url) => url.includes("actor_id=actor-9"))).toBe(true);
      expect(requested.some((url) => url.includes("from=2025-03-01"))).toBe(true);
    });
  });

  it("clears the filters", async () => {
    const fetchMock = stub({
      "GET /admin/audit-events": {
        payload: { items: [auditEvent()], meta: { limit: 25, offset: 0, count: 1 } },
      },
    });

    render(<AuditLog />);
    await waitFor(() => expect(screen.getByText("ADMIN_SUSPENDED")).toBeInTheDocument());

    await userEvent.type(screen.getByLabelText("Event type"), "ADMIN_SUSPENDED");
    await userEvent.click(screen.getByRole("button", { name: "Filter" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).includes("event_type=ADMIN_SUSPENDED")),
      ).toBe(true),
    );

    await userEvent.click(screen.getByRole("button", { name: "Clear" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => !String(url).includes("event_type=")),
      ).toBe(true),
    );
  });

  it("shows the empty state when the filter matches nothing", async () => {
    stub({
      "GET /admin/audit-events": {
        payload: { items: [], meta: { limit: 25, offset: 0, count: 0 } },
      },
    });

    render(<AuditLog />);

    await waitFor(() => expect(screen.getByText(/No audit events/i)).toBeInTheDocument());
  });

  it("surfaces a rejected filter as an error", async () => {
    stub({
      "GET /admin/audit-events": {
        payload: { error: { code: "validation_error", message: "Unknown event type." } },
        status: 422,
      },
    });

    render(<AuditLog />);

    await waitFor(() =>
      expect(screen.getByRole("region", { name: /went wrong/i })).toBeInTheDocument(),
    );
  });
});
