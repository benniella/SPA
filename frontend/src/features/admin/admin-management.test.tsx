import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AdministratorDetail } from "@/features/admin";
import { AdministratorList } from "@/features/admin";
import { AuditLog } from "@/features/admin";

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers(),
    json: async () => payload,
  } as Response;
}

function admin(overrides: Record<string, unknown> = {}) {
  return {
    id: "admin-1",
    user_id: "user-1",
    email: "target@example.com",
    status: "active",
    roles: ["support_admin"],
    privileges: ["users.read"],
    mfa_enrolled: true,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
    ...overrides,
  };
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

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
});

describe("administrator list", () => {
  it("renders administrators and links each to its detail page", async () => {
    stub({
      "GET /admin/administrators": {
        payload: {
          items: [
            admin(),
            admin({ id: "admin-2", email: "second@example.com", status: "invited" }),
          ],
          meta: { limit: 200, offset: 0, count: 2 },
        },
      },
    });

    render(<AdministratorList />);

    await waitFor(() => expect(screen.getByText("target@example.com")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "target@example.com" })).toHaveAttribute(
      "href",
      "/admin/administrators/admin-1",
    );
    expect(screen.getByText("invited")).toBeInTheDocument();
  });

  it("shows the empty state when there are no administrators", async () => {
    stub({
      "GET /admin/administrators": {
        payload: { items: [], meta: { limit: 200, offset: 0, count: 0 } },
      },
    });

    render(<AdministratorList />);

    await waitFor(() => expect(screen.getByText(/No administrators yet/i)).toBeInTheDocument());
  });

  it("shows the error state when the list request fails", async () => {
    stub({
      "GET /admin/administrators": {
        payload: { error: { code: "permission_denied", message: "Nope." } },
        status: 403,
      },
    });

    render(<AdministratorList />);

    await waitFor(() =>
      expect(screen.getByRole("region", { name: /went wrong/i })).toBeInTheDocument(),
    );
  });
});

describe("administrator detail", () => {
  function detailRoutes(extra: Record<string, RouteReply> = {}) {
    return {
      "GET /admin/administrators/admin-1/roles": { payload: { items: ["support_admin"] } },
      "GET /admin/administrators/admin-1": { payload: admin() },
      "GET /admin/roles": { payload: { items: ["support_admin", "finance_admin"] } },
      "GET /admin/privileges": { payload: { items: ["users.read", "billing.read"] } },
      ...extra,
    };
  }

  it("shows the record, its roles and its privileges", async () => {
    stub(detailRoutes());

    render(<AdministratorDetail administratorId="admin-1" />);

    await waitFor(() => expect(screen.getByText("target@example.com")).toBeInTheDocument());
    expect(screen.getByRole("checkbox", { name: "support_admin" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "finance_admin" })).not.toBeChecked();
    expect(screen.getByText("users.read")).toBeInTheDocument();
  });

  it("sends the complete role set on save", async () => {
    const fetchMock = stub(
      detailRoutes({
        "PUT /admin/administrators/admin-1/roles": { payload: { items: ["finance_admin"] } },
      }),
    );

    render(<AdministratorDetail administratorId="admin-1" />);
    await waitFor(() =>
      expect(screen.getByRole("checkbox", { name: "finance_admin" })).toBeInTheDocument(),
    );

    await userEvent.click(screen.getByRole("checkbox", { name: "finance_admin" }));
    await userEvent.click(screen.getByRole("button", { name: /Save roles/i }));

    const putCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/roles") && (init as RequestInit | undefined)?.method === "PUT",
    );
    expect(putCall).toBeTruthy();
    expect(JSON.parse((putCall?.[1] as RequestInit).body as string)).toEqual({
      roles: ["support_admin", "finance_admin"],
    });
  });

  it("surfaces a backend authorization failure instead of hiding it", async () => {
    stub(
      detailRoutes({
        "PUT /admin/administrators/admin-1/roles": {
          payload: {
            error: { code: "permission_denied", message: "Privilege admins.manage is required." },
          },
          status: 403,
        },
      }),
    );

    render(<AdministratorDetail administratorId="admin-1" />);
    await waitFor(() =>
      expect(screen.getByRole("checkbox", { name: "finance_admin" })).toBeInTheDocument(),
    );

    await userEvent.click(screen.getByRole("checkbox", { name: "finance_admin" }));
    await userEvent.click(screen.getByRole("button", { name: /Save roles/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/Not permitted/i));
  });

  it("suspends an active administrator", async () => {
    const fetchMock = stub(
      detailRoutes({
        "POST /admin/administrators/admin-1/suspend": { payload: admin({ status: "suspended" }) },
      }),
    );

    render(<AdministratorDetail administratorId="admin-1" />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Suspend" })).toBeInTheDocument(),
    );

    await userEvent.click(screen.getByRole("button", { name: "Suspend" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/suspend"))).toBe(true),
    );
  });

  it("offers reactivation for a suspended administrator", async () => {
    stub(
      detailRoutes({
        "GET /admin/administrators/admin-1": { payload: admin({ status: "suspended" }) },
      }),
    );

    render(<AdministratorDetail administratorId="admin-1" />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Reactivate" })).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: "Suspend" })).not.toBeInTheDocument();
  });

  it("requires confirmation before revoking", async () => {
    stub(detailRoutes());

    render(<AdministratorDetail administratorId="admin-1" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Revoke" })).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Revoke" }));

    const dialog = screen.getByRole("alertdialog", { name: /Confirm revocation/i });
    expect(within(dialog).getByText(/permanent/i)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: /Yes, revoke/i })).toBeInTheDocument();
  });

  it("shows a conflict when the lifecycle transition is no longer valid", async () => {
    stub(
      detailRoutes({
        "POST /admin/administrators/admin-1/suspend": {
          payload: {
            error: {
              code: "conflict",
              message: "Administrator is suspended, not one of ('active',).",
            },
          },
          status: 409,
        },
      }),
    );

    render(<AdministratorDetail administratorId="admin-1" />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Suspend" })).toBeInTheDocument(),
    );

    await userEvent.click(screen.getByRole("button", { name: "Suspend" }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });

  it("shows the error state when the detail request fails", async () => {
    stub({
      "GET /admin/administrators/admin-1": {
        payload: { error: { code: "not_found", message: "Does not exist." } },
        status: 404,
      },
    });

    render(<AdministratorDetail administratorId="admin-1" />);

    await waitFor(() =>
      expect(screen.getByRole("region", { name: /went wrong/i })).toBeInTheDocument(),
    );
  });
});

describe("audit log", () => {
  it("renders events with their type, actor and timestamp", async () => {
    stub({
      "GET /admin/audit-events": {
        payload: {
          items: [
            {
              id: "e1",
              actor_id: "actor-1",
              event_type: "ADMIN_SUSPENDED",
              metadata: { from: "active", to: "suspended" },
              created_at: "2025-03-04T10:00:00Z",
            },
          ],
          meta: { limit: 25, offset: 0, count: 1 },
        },
      },
    });

    render(<AuditLog />);

    await waitFor(() => expect(screen.getByText("ADMIN_SUSPENDED")).toBeInTheDocument());
    expect(screen.getByText(/Actor actor-1/)).toBeInTheDocument();
    expect(screen.getByText(/from: active/)).toBeInTheDocument();
  });

  it("shows an empty state when no events match", async () => {
    stub({
      "GET /admin/audit-events": {
        payload: { items: [], meta: { limit: 25, offset: 0, count: 0 } },
      },
    });

    render(<AuditLog />);

    await waitFor(() => expect(screen.getByText(/No audit events/i)).toBeInTheDocument());
  });

  it("requests the next page when paginating", async () => {
    const fetchMock = stub({
      "GET /admin/audit-events": {
        payload: {
          items: Array.from({ length: 25 }, (_, index) => ({
            id: `e${index}`,
            actor_id: null,
            event_type: "ADMIN_INVITATION_CREATED",
            metadata: {},
            created_at: "2025-03-04T10:00:00Z",
          })),
          meta: { limit: 25, offset: 0, count: 25 },
        },
      },
    });

    render(<AuditLog />);
    await waitFor(() =>
      expect(screen.getAllByText("ADMIN_INVITATION_CREATED").length).toBeGreaterThan(0),
    );

    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("offset=25"))).toBe(true),
    );
  });
});
