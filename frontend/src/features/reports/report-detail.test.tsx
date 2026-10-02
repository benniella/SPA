import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionProvider } from "@/features/auth/session";
import { ReportDetail } from "@/features/reports";
import type { AuthenticatedUser, Organization, ReportDetail as ReportDetailRecord } from "@/types/api";

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

function report(overrides: Partial<ReportDetailRecord> = {}): ReportDetailRecord {
  const base: ReportDetailRecord = {
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
    content: {
      definition_version: "v1",
      overview: {
        analysis_run_id: "run-1",
        analysis_status: "succeeded",
        video_id: "video-1",
        video_filename: "match.mp4",
        match_id: null,
        analysis_created_at: "2025-01-01T00:00:00Z",
        analysis_finished_at: "2025-01-01T00:02:00Z",
        source_width: 1920,
        source_height: 1080,
        observation_count: 120,
        track_count: 2,
        metric_definition_version: "v1",
        space: "source",
      },
      tracks: [
        {
          track_id: 1,
          space: "source",
          metrics: [
            {
              name: "observation_count",
              unit: "count",
              availability: "available",
              value: 120,
              sample_count: 120,
            },
            {
              name: "displacement",
              unit: "pixels",
              availability: "available",
              value: 1240,
              sample_count: 119,
            },
            {
              name: "peak_speed",
              unit: "pixels_per_second",
              availability: "unavailable",
              value: null,
              sample_count: 1,
            },
          ],
        },
      ],
      observations: [
        {
          type: "highest_observation_count",
          track_ids: [1],
          metric_name: "observation_count",
          unit: "count",
          space: "source",
          value: 120,
          message:
            "Track 1 has the highest observed observation count in this analysis: 120.",
        },
      ],
      limitations: [
        "Measurements are reported in source-video space (pixels), not physical distance or speed.",
      ],
    },
  };
  return { ...base, ...overrides };
}

interface Route {
  status?: number;
  payload: unknown;
}

function stubApi(routes: Record<string, Route>) {
  const allRoutes: Record<string, Route> = { "GET /auth/me": { payload: ACCOUNT }, ...routes };
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
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
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderDetail() {
  window.localStorage.setItem("spa.workspace", ORGANIZATION.id);
  return render(
    <SessionProvider>
      <ReportDetail reportId="report-1" />
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

describe("ReportDetail", () => {
  it("shows the report's stored overview from the API", async () => {
    stubApi({
      ...ORGANIZATIONS_ROUTE,
      "GET /reports/report-1": { payload: report() },
    });

    renderDetail();

    await waitFor(() => expect(screen.getByText("Analysis overview")).toBeInTheDocument());
    expect(screen.getByText("match.mp4")).toBeInTheDocument();
    expect(screen.getAllByText("1,920 × 1,080 px").length).toBeGreaterThan(0);
    expect(screen.getByText("Analysis report — run 12345678")).toBeInTheDocument();
  });

  it("states that measurements are in source-video space", async () => {
    stubApi({
      ...ORGANIZATIONS_ROUTE,
      "GET /reports/report-1": { payload: report() },
    });

    renderDetail();

    await waitFor(() =>
      expect(screen.getAllByText(/source-video space \(pixels\)/).length).toBeGreaterThan(0),
    );
  });

  it("renders a track summary from the persisted metrics", async () => {
    stubApi({
      ...ORGANIZATIONS_ROUTE,
      "GET /reports/report-1": { payload: report() },
    });

    renderDetail();

    await waitFor(() => expect(screen.getByText("Track summary")).toBeInTheDocument());
    expect(screen.getByText("1,240 px")).toBeInTheDocument();
  });

  it("keeps an unavailable metric unavailable rather than zero", async () => {
    stubApi({
      ...ORGANIZATIONS_ROUTE,
      "GET /reports/report-1": { payload: report() },
    });

    renderDetail();

    await waitFor(() => expect(screen.getByText("Unavailable")).toBeInTheDocument());
  });

  it("renders the deterministic data observations", async () => {
    stubApi({
      ...ORGANIZATIONS_ROUTE,
      "GET /reports/report-1": { payload: report() },
    });

    renderDetail();

    await waitFor(() =>
      expect(
        screen.getByText(
          "Track 1 has the highest observed observation count in this analysis: 120.",
        ),
      ).toBeInTheDocument(),
    );
  });

  it("does not render a contents section while the report is generating", async () => {
    stubApi({
      ...ORGANIZATIONS_ROUTE,
      "GET /reports/report-1": {
        payload: report({ status: "generating", generated_at: null, content: null }),
      },
    });

    renderDetail();

    await waitFor(() =>
      expect(screen.getByText("This report is still being generated")).toBeInTheDocument(),
    );
    expect(screen.queryByText("Data observations")).not.toBeInTheDocument();
  });

  it("reports a failed generation", async () => {
    stubApi({
      ...ORGANIZATIONS_ROUTE,
      "GET /reports/report-1": {
        payload: report({
          status: "failed",
          generated_at: null,
          content: null,
          error_message: "Report generation failed.",
        }),
      },
    });

    renderDetail();

    await waitFor(() =>
      expect(screen.getByText("This report could not be generated")).toBeInTheDocument(),
    );
  });

  it("reports a failed load", async () => {
    stubApi({
      ...ORGANIZATIONS_ROUTE,
      "GET /reports/report-1": {
        status: 500,
        payload: { error: { code: "internal_error", message: "Something went wrong." } },
      },
    });

    renderDetail();

    await waitFor(() => expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument());
  });

  it("states that a downloadable document is not available", async () => {
    stubApi({
      ...ORGANIZATIONS_ROUTE,
      "GET /reports/report-1": { payload: report() },
    });

    renderDetail();

    await waitFor(() => expect(screen.getByText("No document to download")).toBeInTheDocument());
  });
});
