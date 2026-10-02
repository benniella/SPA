import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AnalysisMetricsPanel } from "@/features/analysis/components/analysis-metrics-panel";
import { SessionProvider } from "@/features/auth/session";
import type {AuthenticatedUser,  AnalysisMetrics, Organization } from "@/types/api";

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

function metrics(overrides: Partial<AnalysisMetrics> = {}): AnalysisMetrics {
  const base: AnalysisMetrics = {
    analysis_run_id: "run-1",
    organization_id: ORGANIZATION.id,
    space: "source",
    definition_version: "v1",
    track_count: 1,
    tracks: [
      {
        track_id: 7,
        space: "source",
        metrics: [
          {
            name: "observation_count",
            unit: "count",
            space: "source",
            availability: "available",
            value: 4,
            sample_count: 4,
          },
          {
            name: "duration",
            unit: "seconds",
            space: "source",
            availability: "available",
            value: 1.5,
            sample_count: 4,
          },
          {
            name: "displacement",
            unit: "pixels",
            space: "source",
            availability: "available",
            value: 30,
            sample_count: 3,
          },
          {
            name: "average_speed",
            unit: "pixels_per_second",
            space: "source",
            availability: "available",
            value: 20,
            sample_count: 3,
          },
          {
            name: "peak_speed",
            unit: "pixels_per_second",
            space: "source",
            availability: "unavailable",
            value: null,
            sample_count: 1,
          },
          {
            name: "coverage",
            unit: "count",
            space: "source",
            availability: "available",
            value: 1,
            sample_count: 4,
          },
          {
            name: "mean_confidence",
            unit: "count",
            space: "source",
            availability: "available",
            value: 0.9,
            sample_count: 4,
          },
        ],
      },
    ],
    generated_at: "2025-01-01T00:05:00Z",
  };
  return { ...base, ...overrides };
}

interface Route {
  status?: number;
  payload: unknown;
}

function stubApi(routes: Record<string, Route>) {
  const calls: string[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input));
    if (url.pathname === "/api/v1/auth/me") {
      return { ok: true, status: 200, headers: new Headers(), json: async () => ACCOUNT } as Response;
    }

    const method = init?.method ?? "GET";
    calls.push(`${method} ${url.pathname}`);
    for (const [key, route] of Object.entries(routes)) {
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
  });
  vi.stubGlobal("fetch", fetchMock);
  return calls;
}

function renderPanel() {
  window.localStorage.setItem("spa.workspace", ORGANIZATION.id);
  return render(
    <SessionProvider>
      <AnalysisMetricsPanel runId="run-1" />
    </SessionProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe("AnalysisMetricsPanel", () => {
  it("shows each metric with its unit", async () => {
    stubApi({
      "GET /organizations": {
        payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
      },
      "GET /analysis-runs/run-1/metrics": { payload: metrics() },
    });

    renderPanel();

    await waitFor(() => expect(screen.getByText("30 px")).toBeInTheDocument());
    expect(screen.getByText("20 px/s")).toBeInTheDocument();
    expect(screen.getByText("1.5 s")).toBeInTheDocument();
  });

  it("states that the metrics are source-space pixels, not metres", async () => {
    stubApi({
      "GET /organizations": {
        payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
      },
      "GET /analysis-runs/run-1/metrics": { payload: metrics() },
    });

    renderPanel();

    await waitFor(() =>
      expect(screen.getByText(/Source image pixels — not calibrated/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/pixels are not metres/)).toBeInTheDocument();
  });

  it("shows an unavailable metric as unavailable rather than zero", async () => {
    stubApi({
      "GET /organizations": {
        payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
      },
      "GET /analysis-runs/run-1/metrics": { payload: metrics() },
    });

    renderPanel();

    await waitFor(() => expect(screen.getByText("Unavailable")).toBeInTheDocument());
    expect(screen.queryByText("0 px/s")).toBeNull();
  });

  it("shows an empty state when the run has produced no metrics", async () => {
    stubApi({
      "GET /organizations": {
        payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
      },
      "GET /analysis-runs/run-1/metrics": { payload: metrics({ tracks: [], track_count: 0 }) },
    });

    renderPanel();

    await waitFor(() => expect(screen.getByText("No metrics available")).toBeInTheDocument());
  });

  it("offers calculation when the metrics stage has not run yet", async () => {
    stubApi({
      "GET /organizations": {
        payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
      },
      "GET /analysis-runs/run-1/metrics": {
        status: 409,
        payload: { error: { code: "conflict", message: "This run has no metrics." } },
      },
    });

    renderPanel();

    await waitFor(() => expect(screen.getByText("No metrics calculated yet")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Calculate metrics" })).toBeInTheDocument();
  });

  it("queues calculation and re-reads", async () => {
    const calls = stubApi({
      "GET /organizations": {
        payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
      },
      "GET /analysis-runs/run-1/metrics": {
        status: 409,
        payload: { error: { code: "conflict", message: "This run has no metrics." } },
      },
      "POST /analysis-runs/run-1/metrics": {
        status: 202,
        payload: {
          analysis_run_id: "run-1",
          job_id: "job-1",
          status: "queued",
          progress: 0,
        },
      },
    });

    renderPanel();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Calculate metrics" })).toBeInTheDocument(),
    );

    await userEvent.click(screen.getByRole("button", { name: "Calculate metrics" }));

    await waitFor(() => expect(calls).toContain("POST /api/v1/analysis-runs/run-1/metrics"));
  });
});
