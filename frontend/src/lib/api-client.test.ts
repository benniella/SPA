import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, NetworkError, api, readLocationHeader } from "@/lib/api-client";

/** Minimal stand-in for 'fetch' that returns a canned response. */
function mockFetch(response: Partial<Response> & { json?: () => Promise<unknown> }) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    headers: new Headers(),
    json: async () => ({}),
    ...response,
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("api.get", () => {
  it("parses a successful JSON response", async () => {
    mockFetch({ json: async () => ({ status: "ok" }) });

    await expect(api.get<{ status: string }>("/health")).resolves.toEqual({ status: "ok" });
  });

  it("returns undefined for 204 rather than throwing on an empty body", async () => {
    mockFetch({ status: 204 });

    await expect(api.delete<void>("/videos/abc")).resolves.toBeUndefined();
  });
});

describe("error handling", () => {
  it("maps the backend error envelope onto ApiError", async () => {
    mockFetch({
      ok: false,
      status: 404,
      json: async () => ({
        error: { code: "not_found", message: "Video abc does not exist." },
      }),
    });

    const error = await api.get("/videos/abc").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("not_found");
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).isRetryable).toBe(false);
  });

  it("falls back to the status when a non-JSON body arrives", async () => {
    // A reverse proxy returning an HTML error page is common in production and
    // must not surface as a JSON parse failure.
    mockFetch({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: async () => {
        throw new SyntaxError("Unexpected token '<'");
      },
    });

    const error = (await api.get("/health").catch((e: unknown) => e)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toBe("Bad Gateway");
    expect(error.isRetryable).toBe(true);
  });

  it("reports a network failure distinctly from an API rejection", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    // "The API said no" and "the API was not reachable" need different messages.
    await expect(api.get("/health")).rejects.toBeInstanceOf(NetworkError);
  });

  it("exposes field-level validation errors", async () => {
    mockFetch({
      ok: false,
      status: 422,
      json: async () => ({
        error: {
          code: "validation_error",
          message: "The request payload is invalid.",
          details: {
            errors: [{ location: ["body", "slug"], message: "String should match pattern" }],
          },
        },
      }),
    });

    const error = (await api.post("/organizations", {}).catch((e: unknown) => e)) as ApiError;

    expect(error.fieldErrors).toEqual([
      { location: ["body", "slug"], message: "String should match pattern" },
    ]);
  });

  it("tolerates an error code it does not know", async () => {
    // A newer backend must not break an older client: the code is kept verbatim
    // rather than collapsed into a generic failure.
    mockFetch({
      ok: false,
      status: 418,
      json: async () => ({ error: { code: "teapot", message: "Short and stout." } }),
    });

    const error = (await api.get("/health").catch((e: unknown) => e)) as ApiError;

    expect(error.code).toBe("teapot");
  });
});

describe("request construction", () => {
  it("sends JSON with the right content type", async () => {
    const fetchMock = mockFetch({ json: async () => ({}) });

    await api.post("/organizations", { name: "Acme" });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/organizations");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ name: "Acme" }));
  });

  it("omits a body and content type for GET", async () => {
    const fetchMock = mockFetch({ json: async () => ({}) });

    await api.get("/health");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBeUndefined();
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });
});

describe("readLocationHeader", () => {
  it("returns the Location header when present", () => {
    // 202 Accepted is only useful to a client if it can find the resource.
    const response = new Response(null, {
      status: 202,
      headers: { Location: "/api/v1/analysis-runs/abc" },
    });

    expect(readLocationHeader(response)).toBe("/api/v1/analysis-runs/abc");
  });

  it("returns null when absent", () => {
    expect(readLocationHeader(new Response(null, { status: 202 }))).toBeNull();
  });
});
