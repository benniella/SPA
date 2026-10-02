import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionProvider } from "@/features/auth/session";
import { ReportList } from "@/features/reports";
import type { AuthenticatedUser, Organization, Report } from "@/types/api";

const ORGANIZATION: Organization = {
  id: "org-1",
  name: "Riverside FC",
  slug: "riverside-fc",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

const ACCOUNT: AuthenticatedUser = {
  id: "user-1",
  email: "coach@club.example",
  display_name: "Coach",
  account_status: "active",
  email_verified: true,
  phone_verified: false,
  phone_number: null,
  created_at: "2025-01-01T00:00:00Z",
  last_login_at: null,
  organizations: [
    { id: ORGANIZATION.id, name: ORGANIZATION.name, slug: ORGANIZATION.slug, role: "owner" },
  ],
};

function report(overrides: Partial<Report> = {}): Report {
  const base: Report = {
    id: "report-1",
    organization_id: ORGANIZATION.id,
    created_by_id: null,
    title: "Analysis report — run 12345678",
    status: "ready",
    definition_version: "v1",
    analysis_run_id: "run-1",
    match_id: null,
    team_id: null,
    storage_key: null,
    error_message: null,
    generated_at: "2025-01-01T00:05:00Z",
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:05:00Z",
  };
  return { ...base, ...overrides };
}

interface Route {
  status?: number;
  payload: unknown;
}

function stubApi(routes: Record<string, Route>) {
  const allRoutes: Record<string, Route> = { "GET /auth/me": { payload: ACCOUNT }, ...routes };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
    if (url.pathname === "/api/v1/auth/me") {
      return { ok: true, status: 200, headers: new Headers(), json: async () => ACCOUNT } as Response;
    }

      const method = init?.method ?? "GET";
      for (const [key, route] of Object.entries(allRoutes)) {
        const [routeMethod, routePath] = key.split(" ");
        if (url.pathname === `/api/v1${routePath}` && method === routeMethod) {
          const status = route.status ?? 200;
          return {
            ok: status < 400,
            status,
            headers: new Headers(),
            json: async () => route.payload,
          } as Response;
        }
      }
      return {
        ok: false,
        status: 404,
        headers: new Headers(),
        json: async () => ({ error: { code: "not_found", message: "No stub route." } }),
      } as Response;
    }),
  );
}

function renderList() {
  window.localStorage.setItem("spa.workspace", ORGANIZATION.id);
  return render(
    <SessionProvider>
      <ReportList />
    </SessionProvider>,
  );
}

const ORGANIZATIONS_ROUTE = {
  "GET /organizations": {
    payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
  },
};

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe("ReportList", () => {
  it("lists the workspace's real reports", async () => {
    stubApi({
      ...ORGANIZATIONS_ROUTE,
      "GET /reports": {
        payload: {
          items: [report()],
          meta: { limit: 200, offset: 0, count: 1 },
        },
      },
    });

    renderList();

    await waitFor(() =>
      expect(screen.getByText("Analysis report — run 12345678")).toBeInTheDocument(),
    );
    expect(screen.getByText("1 report in this workspace.")).toBeInTheDocument();
  });

  it("shows an empty state when there are no reports", async () => {
    stubApi({
      ...ORGANIZATIONS_ROUTE,
      "GET /reports": { payload: { items: [], meta: { limit: 200, offset: 0, count: 0 } } },
    });

    renderList();

    await waitFor(() => expect(screen.getByText("No reports yet")).toBeInTheDocument());
  });

  it("reports a failed load", async () => {
    stubApi({
      ...ORGANIZATIONS_ROUTE,
      "GET /reports": {
        status: 500,
        payload: { error: { code: "internal_error", message: "Something went wrong." } },
      },
    });

    renderList();

    await waitFor(() => expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument());
  });

  it("shows a generating report's status", async () => {
    stubApi({
      ...ORGANIZATIONS_ROUTE,
      "GET /reports": {
        payload: {
          items: [report({ status: "generating", generated_at: null })],
          meta: { limit: 200, offset: 0, count: 1 },
        },
      },
    });

    renderList();

    await waitFor(() => expect(screen.getByText("Generating")).toBeInTheDocument());
  });
});
