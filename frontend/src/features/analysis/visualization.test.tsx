import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AnalysisVisualizationPanel } from "@/features/analysis/components/analysis-visualization-panel";
import { SessionProvider } from "@/features/auth/session";
import type { Organization, RunVisualization } from "@/types/api";

const ORGANIZATION: Organization = {
  id: "org-1",
  name: "Riverside FC",
  slug: "riverside-fc",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

function visualization(overrides: Partial<RunVisualization> = {}): RunVisualization {
  const base: RunVisualization = {
    analysis_run_id: "run-1",
    organization_id: ORGANIZATION.id,
    status: "succeeded",
    space: "source",
    frame: { width: 1920, height: 1080 },
    observation_count: 4,
    track_count: 2,
    paths: [
      {
        track_id: 1,
        observation_count: 3,
        downsampled: false,
        start_seconds: 0,
        end_seconds: 1,
        points: [
          { frame_index: 0, timestamp_seconds: 0, x: 100, y: 200, confidence: 0.9 },
          { frame_index: 1, timestamp_seconds: 0.5, x: 200, y: 300, confidence: 0.9 },
          { frame_index: 2, timestamp_seconds: 1, x: 300, y: 400, confidence: 0.9 },
        ],
      },
      {
        track_id: 2,
        observation_count: 1,
        downsampled: false,
        start_seconds: 0,
        end_seconds: 0,
        points: [{ frame_index: 0, timestamp_seconds: 0, x: 900, y: 500, confidence: 0.8 }],
      },
    ],
    density: {
      columns: 2,
      rows: 2,
      counts: [3, 0, 0, 1],
      max_count: 3,
      bounds: [0, 0, 1920, 1080],
      observation_count: 4,
      track_count: 2,
    },
    timeline: {
      bucket_seconds: 5,
      start_seconds: 0,
      end_seconds: 1,
      max_count: 3,
      buckets: [
        {
          index: 0,
          start_seconds: 0,
          end_seconds: 5,
          observation_count: 4,
          track_ids: [1, 2],
        },
      ],
    },
    metrics: {
      analysis_run_id: "run-1",
      organization_id: ORGANIZATION.id,
      space: "source",
      definition_version: "v1",
      track_count: 1,
      tracks: [
        {
          track_id: 1,
          space: "source",
          metrics: [
            {
              name: "observation_count",
              unit: "count",
              space: "source",
              availability: "available",
              value: 3,
              sample_count: 3,
            },
            {
              name: "displacement",
              unit: "pixels",
              space: "source",
              availability: "available",
              value: 60,
              sample_count: 2,
            },
            {
              name: "peak_speed",
              unit: "pixels_per_second",
              space: "source",
              availability: "unavailable",
              value: null,
              sample_count: 1,
            },
          ],
        },
      ],
      generated_at: "2025-01-01T00:05:00Z",
    },
  };
  return { ...base, ...overrides };
}

interface Route {
  status?: number;
  payload: unknown;
}

function stubApi(routes: Record<string, Route>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input));
    const method = init?.method ?? "GET";
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
  return fetchMock;
}

function renderPanel() {
  window.localStorage.setItem("spa.dev.workspace", ORGANIZATION.id);
  return render(
    <SessionProvider>
      <AnalysisVisualizationPanel runId="run-1" />
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

describe("AnalysisVisualizationPanel", () => {
  it("states the visualization is in source-video pixels, not metres", async () => {
    stubApi({
      "GET /organizations": {
        payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
      },
      "GET /analysis-runs/run-1/visualization": { payload: visualization() },
    });

    renderPanel();

    await waitFor(() =>
      expect(screen.getByText("Source-video pixels — not calibrated")).toBeInTheDocument(),
    );
    expect(screen.getByText(/these are not metres/)).toBeInTheDocument();
    expect(screen.getByText("1,920 × 1,080 px")).toBeInTheDocument();
  });

  it("renders a path element per track from the returned coordinates", async () => {
    stubApi({
      "GET /organizations": {
        payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
      },
      "GET /analysis-runs/run-1/visualization": { payload: visualization() },
    });

    const { container } = renderPanel();

    await waitFor(() => expect(screen.getByRole("tab", { name: "Track paths" })).toBeInTheDocument());
    const paths = container.querySelectorAll("svg .viz-track path");
    expect(paths).toHaveLength(2);
    // The first segment of track 1 begins at its first observed coordinate.
    expect(paths[0]?.getAttribute("d")).toContain("M 100 200");
  });

  it("draws the density grid without one element per observation", async () => {
    stubApi({
      "GET /organizations": {
        payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
      },
      "GET /analysis-runs/run-1/visualization": { payload: visualization() },
    });

    const { container } = renderPanel();

    await waitFor(() => expect(screen.getByRole("tab", { name: "Spatial density" })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("tab", { name: "Spatial density" }));

    // Two non-empty cells out of four; empty cells are not drawn at all.
    const cells = container.querySelectorAll(".viz-frame-surface rect:not(.viz-frame-backdrop)");
    expect(cells).toHaveLength(2);
  });

  it("selects a track and shows its metrics without refetching", async () => {
    const fetchMock = stubApi({
      "GET /organizations": {
        payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
      },
      "GET /analysis-runs/run-1/visualization": { payload: visualization() },
    });

    renderPanel();

    await waitFor(() => expect(screen.getByText("Select a track to see the metrics derived for it.")).toBeInTheDocument());

    const selector = screen
      .getAllByRole("button")
      .find((button) => button.getAttribute("aria-pressed") !== null && /^Track 1/.test(button.textContent ?? ""));
    expect(selector).toBeDefined();
    await userEvent.click(selector as HTMLElement);

    await waitFor(() => expect(screen.getByText("60 px")).toBeInTheDocument());
    expect(screen.getByText("Unavailable")).toBeInTheDocument();

    // Selecting a track is local state: only the initial read hits the network.
    const visualizationCalls = fetchMock.mock.calls.filter((call) =>
      String(call[0]).includes("/visualization"),
    );
    expect(visualizationCalls).toHaveLength(1);
  });

  it("shows a conflict as an honest no-data state", async () => {
    stubApi({
      "GET /organizations": {
        payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
      },
      "GET /analysis-runs/run-1/visualization": {
        status: 409,
        payload: { error: { code: "conflict", message: "The run has no tracking data." } },
      },
    });

    renderPanel();

    await waitFor(() =>
      expect(screen.getByText("Tracking data is not available yet")).toBeInTheDocument(),
    );
  });

  it("shows an empty state when the run produced no observations", async () => {
    stubApi({
      "GET /organizations": {
        payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
      },
      "GET /analysis-runs/run-1/visualization": {
        payload: visualization({
          observation_count: 0,
          track_count: 0,
          paths: [],
          density: {
            columns: 2,
            rows: 2,
            counts: [0, 0, 0, 0],
            max_count: 0,
            bounds: [0, 0, 1920, 1080],
            observation_count: 0,
            track_count: 0,
          },
          timeline: {
            bucket_seconds: 5,
            start_seconds: 0,
            end_seconds: 0,
            max_count: 0,
            buckets: [],
          },
        }),
      },
    });

    renderPanel();

    await waitFor(() =>
      expect(screen.getByText("No track observations were produced")).toBeInTheDocument(),
    );
  });

  it("reports a failed visualization load", async () => {
    stubApi({
      "GET /organizations": {
        payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
      },
      "GET /analysis-runs/run-1/visualization": {
        status: 500,
        payload: { error: { code: "internal_error", message: "Something went wrong." } },
      },
    });

    renderPanel();

    await waitFor(() => expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument());
  });

  it("shows the activity timeline as observation counts", async () => {
    stubApi({
      "GET /organizations": {
        payload: { items: [ORGANIZATION], meta: { limit: 50, offset: 0, count: 1 } },
      },
      "GET /analysis-runs/run-1/visualization": { payload: visualization() },
    });

    renderPanel();

    await userEvent.click(await screen.findByRole("tab", { name: "Activity" }));

    expect(await screen.findByLabelText(/0\.0s to 5\.0s: 4 observations/)).toBeInTheDocument();
  });
});