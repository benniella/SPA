import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionProvider } from "@/features/auth/session";
import { VideoLibrary } from "@/features/videos";
import type { Organization, Video } from "@/types/api";

const ORGANIZATION: Organization = {
  id: "org-1",
  name: "Riverside FC",
  slug: "riverside-fc",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

const VIDEO: Video = {
  id: "video-1",
  organization_id: ORGANIZATION.id,
  match_id: null,
  original_filename: "first-half.mp4",
  status: "uploaded",
  content_type: "video/mp4",
  size_bytes: 4096,
  duration_seconds: null,
  frame_rate: null,
  width: null,
  height: null,
  codec: null,
  failure_reason: null,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

interface Recorded {
  method: string;
  path: string;
  body: unknown;
}

function stubApi(routes: Record<string, unknown>) {
  const calls: Recorded[] = [];

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input));
    const method = init?.method ?? "GET";
    calls.push({
      method,
      path: url.pathname,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    });

    for (const [key, payload] of Object.entries(routes)) {
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

function stubUpload({ fail = false } = {}) {
  const requests: Array<{ method: string; url: string; body: unknown }> = [];

  class FakeXHR {
    method = "";
    url = "";
    status = fail ? 500 : 204;
    upload = {
      addEventListener: (_: string, handler: EventListener) => {
        handler(new Event("progress"));
      },
    };
    private listeners: Record<string, EventListener[]> = {};

    open(method: string, url: string) {
      this.method = method;
      this.url = url;
    }

    setRequestHeader() {}

    addEventListener(type: string, handler: EventListener) {
      (this.listeners[type] ??= []).push(handler);
    }

    send(body: unknown) {
      requests.push({ method: this.method, url: this.url, body });
      const type = fail ? "error" : "load";
      for (const handler of this.listeners[type] ?? []) handler(new Event(type));
    }

    abort() {}
  }

  vi.stubGlobal("XMLHttpRequest", FakeXHR);
  return requests;
}

function withSession(children: React.ReactNode) {
  window.localStorage.setItem("spa.dev.workspace", ORGANIZATION.id);
  return render(<SessionProvider>{children}</SessionProvider>);
}

function page<T>(items: T[]) {
  return { items, meta: { limit: 200, offset: 0, count: items.length } };
}

async function pickFile(name = "first-half.mp4") {
  const input = screen.getByLabelText("Choose a video file to upload");
  const file = new File(["bytes"], name, { type: "video/mp4" });
  await userEvent.upload(input, file);
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe("VideoLibrary upload", () => {
  it("reserves, uploads directly to storage, then confirms", async () => {
    const calls = stubApi({
      "GET /organizations": page([ORGANIZATION]),
      "GET /videos": page([]),
      "POST /videos": {
        video_id: "video-1",
        upload_url: "https://storage.test/org-1/videos/abc/first-half.mp4",
        storage_key: "org-1/videos/abc/first-half.mp4",
        expires_in: 3600,
      },
      "POST /videos/video-1/complete": VIDEO,
    });
    const uploads = stubUpload();

    withSession(<VideoLibrary />);
    await waitFor(() => expect(screen.getByText("Upload video")).toBeInTheDocument());

    await pickFile();

    await waitFor(() =>
      expect(calls.some((call) => call.path === "/api/v1/videos/video-1/complete")).toBe(true),
    );

    expect(uploads).toHaveLength(1);
    expect(uploads[0]?.url).toBe("https://storage.test/org-1/videos/abc/first-half.mp4");
    expect(uploads[0]?.method).toBe("PUT");

    const reservation = calls.find(
      (call) => call.path === "/api/v1/videos" && call.method === "POST",
    );
    expect(reservation?.body).toMatchObject({
      organization_id: ORGANIZATION.id,
      filename: "first-half.mp4",
      content_type: "video/mp4",
    });

    const completion = calls.find((call) => call.path === "/api/v1/videos/video-1/complete");
    expect(completion?.body).toMatchObject({ organization_id: ORGANIZATION.id, size_bytes: 5 });
  });

  it("reports a failed storage transfer and does not confirm", async () => {
    const calls = stubApi({
      "GET /organizations": page([ORGANIZATION]),
      "GET /videos": page([]),
      "POST /videos": {
        video_id: "video-1",
        upload_url: "https://storage.test/org-1/videos/abc/first-half.mp4",
        storage_key: "org-1/videos/abc/first-half.mp4",
        expires_in: 3600,
      },
    });
    stubUpload({ fail: true });

    withSession(<VideoLibrary />);
    await waitFor(() => expect(screen.getByText("Upload video")).toBeInTheDocument());

    await pickFile();

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(calls.some((call) => call.path.endsWith("/complete"))).toBe(false);
  });
});

describe("VideoLibrary delete", () => {
  it("deletes a video after confirmation", async () => {
    const calls = stubApi({
      "GET /organizations": page([ORGANIZATION]),
      "GET /videos": page([VIDEO]),
      "DELETE /videos/video-1": undefined,
    });
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true),
    );

    withSession(<VideoLibrary />);
    await waitFor(() => expect(screen.getByText("first-half.mp4")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(calls.some((call) => call.method === "DELETE")).toBe(true));
  });

  it("does not delete when the confirmation is dismissed", async () => {
    const calls = stubApi({
      "GET /organizations": page([ORGANIZATION]),
      "GET /videos": page([VIDEO]),
    });
    vi.stubGlobal(
      "confirm",
      vi.fn(() => false),
    );

    withSession(<VideoLibrary />);
    await waitFor(() => expect(screen.getByText("first-half.mp4")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(calls.some((call) => call.method === "DELETE")).toBe(false);
  });
});
