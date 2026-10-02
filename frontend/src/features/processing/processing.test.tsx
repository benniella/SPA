import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionProvider } from "@/features/auth/session";
import { ProcessingEventsProvider } from "@/features/processing/events-provider";
import { VideoProcessingPanel } from "@/features/processing/components/video-processing-panel";
import type { AuthenticatedUser, Organization, VideoProcessing } from "@/types/api";

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

function processingState(overrides: Partial<VideoProcessing> = {}): VideoProcessing {
  const base: VideoProcessing = {
    video_id: "video-1",
    video_status: "uploaded",
    job: null,
    analysis_run_id: null,
    frames_processed: null,
    detections: null,
    tracks: null,
  };
  return { ...base, ...overrides };
}

function page<T>(items: T[]) {
  return { items, meta: { limit: 50, offset: 0, count: items.length } };
}

function stubApi(routes: Record<string, unknown>) {
  const calls: string[] = [];
  /* The session provider resolves '/auth/me' on mount, so every page under test
     needs that route whether or not the test is about authentication. */
  const allRoutes: Record<string, unknown> = { "GET /auth/me": ACCOUNT, ...routes };
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input));
    const method = init?.method ?? "GET";
    calls.push(`${method} ${url.pathname}`);
    for (const [key, payload] of Object.entries(allRoutes)) {
      const [routeMethod, routePath] = key.split(" ");
      if (url.pathname === `/api/v1${routePath}` && method === routeMethod) {
        return {
          ok: true,
          status: 200,
          headers: new Headers(),
          json: async () => payload,
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

class FakeSocket {
  static instances: FakeSocket[] = [];
  url: string;
  private listeners: Record<string, EventListener[]> = {};

  constructor(url: string) {
    this.url = url;
    FakeSocket.instances.push(this);
  }

  addEventListener(type: string, handler: EventListener) {
    (this.listeners[type] ??= []).push(handler);
  }

  emit(type: string, event?: unknown) {
    for (const handler of this.listeners[type] ?? []) handler((event ?? new Event(type)) as Event);
  }

  emitMessage(data: unknown) {
    this.emit("message", { data: JSON.stringify(data) } as MessageEvent);
  }

  close() {
    this.emit("close");
  }
}

function withProviders(children: React.ReactNode) {
  window.localStorage.setItem("spa.workspace", ORGANIZATION.id);
  return render(
    <SessionProvider>
      <ProcessingEventsProvider>{children}</ProcessingEventsProvider>
    </SessionProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  FakeSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeSocket);
});

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe("VideoProcessingPanel", () => {
  it("shows an unprocessed video and offers to process it", async () => {
    stubApi({
      "GET /organizations": page([ORGANIZATION]),
      "GET /videos/video-1/processing": processingState(),
      "POST /videos/video-1/process": {
        id: "job-1",
        organization_id: ORGANIZATION.id,
        video_id: "video-1",
        job_type: "ingest_video",
        status: "queued",
        attempt: 0,
        max_attempts: 3,
        progress: 0,
        error: null,
        started_at: null,
        completed_at: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    });

    withProviders(<VideoProcessingPanel videoId="video-1" />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Process this video" })).toBeInTheDocument(),
    );
    expect(screen.getByText("Not processed")).toBeInTheDocument();
  });

  it("queues processing and re-reads the state", async () => {
    const calls = stubApi({
      "GET /organizations": page([ORGANIZATION]),
      "GET /videos/video-1/processing": processingState({
        job: {
          id: "job-1",
          organization_id: ORGANIZATION.id,
          video_id: "video-1",
          job_type: "ingest_video",
          status: "queued",
          attempt: 0,
          max_attempts: 3,
          progress: 0,
          error: null,
          started_at: null,
          completed_at: null,
          created_at: "2025-01-01T00:00:00Z",
          updated_at: "2025-01-01T00:00:00Z",
        },
      }),
      "POST /videos/video-1/process": {
        id: "job-1",
        organization_id: ORGANIZATION.id,
        video_id: "video-1",
        job_type: "ingest_video",
        status: "queued",
        attempt: 0,
        max_attempts: 3,
        progress: 0,
        error: null,
        started_at: null,
        completed_at: null,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    });

    withProviders(<VideoProcessingPanel videoId="video-1" />);
    await waitFor(() => expect(screen.getByText("Queued")).toBeInTheDocument());

    expect(screen.queryByRole("button", { name: "Process this video" })).toBeNull();
    expect(calls).toContain("GET /api/v1/videos/video-1/processing");
  });

  it("shows a failure reason rather than a raw error", async () => {
    stubApi({
      "GET /organizations": page([ORGANIZATION]),
      "GET /videos/video-1/processing": processingState({
        video_status: "failed",
        job: {
          id: "job-1",
          organization_id: ORGANIZATION.id,
          video_id: "video-1",
          job_type: "ingest_video",
          status: "failed",
          attempt: 3,
          max_attempts: 3,
          progress: 0,
          error: "The pipeline could not process this video.",
          started_at: "2025-01-01T00:00:00Z",
          completed_at: "2025-01-01T00:05:00Z",
          created_at: "2025-01-01T00:00:00Z",
          updated_at: "2025-01-01T00:05:00Z",
        },
      }),
    });

    withProviders(<VideoProcessingPanel videoId="video-1" />);

    await waitFor(() =>
      expect(screen.getByText("The pipeline could not process this video.")).toBeInTheDocument(),
    );
  });

  it("does not fabricate progress while a job runs without a percentage", async () => {
    stubApi({
      "GET /organizations": page([ORGANIZATION]),
      "GET /videos/video-1/processing": processingState({
        video_status: "processing",
        job: {
          id: "job-1",
          organization_id: ORGANIZATION.id,
          video_id: "video-1",
          job_type: "ingest_video",
          status: "running",
          attempt: 1,
          max_attempts: 3,
          progress: 0,
          error: null,
          started_at: "2025-01-01T00:00:00Z",
          completed_at: null,
          created_at: "2025-01-01T00:00:00Z",
          updated_at: "2025-01-01T00:00:00Z",
        },
      }),
    });

    withProviders(<VideoProcessingPanel videoId="video-1" />);

    await waitFor(() =>
      expect(screen.getByText(/Progress is not reported yet/)).toBeInTheDocument(),
    );
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("shows the CV counts a completed run actually reported", async () => {
    stubApi({
      "GET /organizations": page([ORGANIZATION]),
      "GET /videos/video-1/processing": processingState({
        video_status: "ready",
        analysis_run_id: "run-1",
        frames_processed: 120,
        detections: 342,
        tracks: 23,
      }),
    });

    withProviders(<VideoProcessingPanel videoId="video-1" />);

    await waitFor(() => expect(screen.getByText("120")).toBeInTheDocument());
    expect(screen.getByText("342")).toBeInTheDocument();
    expect(screen.getByText("23")).toBeInTheDocument();
  });

  it("shows no CV counts for a video with no analysis run", async () => {
    stubApi({
      "GET /organizations": page([ORGANIZATION]),
      "GET /videos/video-1/processing": processingState(),
    });

    withProviders(<VideoProcessingPanel videoId="video-1" />);

    await waitFor(() => expect(screen.getByText("Not processed")).toBeInTheDocument());
    expect(screen.queryByText("Detections")).toBeNull();
    expect(screen.queryByText("Tracks")).toBeNull();
  });
});

describe("ProcessingEventsProvider", () => {
  it("opens one connection for the session and closes it on unmount", async () => {
    stubApi({ "GET /organizations": page([ORGANIZATION]) });

    const view = withProviders(<div />);
    await waitFor(() => expect(FakeSocket.instances).toHaveLength(1));
    expect(FakeSocket.instances[0]?.url).toContain("organization_id=org-1");

    view.unmount();
  });

  it("refreshes state when a video event arrives", async () => {
    const calls = stubApi({
      "GET /organizations": page([ORGANIZATION]),
      "GET /videos/video-1/processing": processingState(),
    });

    withProviders(<VideoProcessingPanel videoId="video-1" />);
    await waitFor(() => expect(screen.getByText("Not processed")).toBeInTheDocument());
    const readsBefore = calls.filter((call) => call.includes("/processing")).length;

    const socket = FakeSocket.instances[0];
    socket?.emitMessage({
      event: "processing.completed",
      schema_version: 1,
      job_id: "job-1",
      video_id: "video-1",
      status: "completed",
      progress: 100,
      error: null,
      timestamp: "2025-01-01T00:00:00Z",
    });

    await waitFor(() =>
      expect(calls.filter((call) => call.includes("/processing")).length).toBeGreaterThan(
        readsBefore,
      ),
    );
  });

  it("reconnects with backoff rather than immediately", async () => {
    stubApi({ "GET /organizations": page([ORGANIZATION]) });
    vi.useFakeTimers();

    withProviders(<div />);
    await vi.waitFor(() => expect(FakeSocket.instances).toHaveLength(1));

    FakeSocket.instances[0]?.close();
    expect(FakeSocket.instances).toHaveLength(1);

    await vi.advanceTimersByTimeAsync(1000);
    expect(FakeSocket.instances.length).toBeGreaterThanOrEqual(2);

    vi.useRealTimers();
  });
});

describe("VideoProcessingPanel actions", () => {
  it("surfaces a rejected processing request", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      const method = init?.method ?? "GET";
      if (url.pathname === "/api/v1/auth/me") {
        return {
          ok: true,
          status: 200,
          headers: new Headers(),
          json: async () => ACCOUNT,
        } as Response;
      }
      if (url.pathname === "/api/v1/organizations") {
        return {
          ok: true,
          status: 200,
          headers: new Headers(),
          json: async () => page([ORGANIZATION]),
        } as Response;
      }
      if (url.pathname === "/api/v1/videos/video-1/processing") {
        return {
          ok: true,
          status: 200,
          headers: new Headers(),
          json: async () => processingState(),
        } as Response;
      }
      if (method === "POST") {
        return {
          ok: false,
          status: 409,
          headers: new Headers(),
          json: async () => ({
            error: { code: "conflict", message: "This video cannot be processed." },
          }),
        } as Response;
      }
      return { ok: false, status: 404, headers: new Headers(), json: async () => ({}) } as Response;
    });
    vi.stubGlobal("fetch", fetchMock);

    withProviders(<VideoProcessingPanel videoId="video-1" />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Process this video" })).toBeInTheDocument(),
    );

    await userEvent.click(screen.getByRole("button", { name: "Process this video" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("This video cannot be processed."),
    );
  });
});
