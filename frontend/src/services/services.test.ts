import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { queryString } from "@/services/query";
import { listPlayers } from "@/services/players";
import { getTeam, listTeams } from "@/services/teams";
import { listAnalysisRuns } from "@/services/analysis";
import { createUser } from "@/services/users";

function mockFetch(json: unknown = { items: [], meta: { limit: 50, offset: 0, count: 0 } }) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    headers: new Headers(),
    json: async () => json,
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function urlOf(fetchMock: ReturnType<typeof vi.fn>, call = 0): string {
  return (fetchMock.mock.calls[call] as [string, RequestInit])[0];
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  vi.stubEnv("NEXT_PUBLIC_API_VERSION_PREFIX", "/api/v1");
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("queryString", () => {
  it("omits null, undefined and empty values", () => {
    // Sending '?team_id=' fails UUID validation where an absent 'team_id' means
    // "no filter" — so omission is the correct behaviour, not a nicety.
    expect(queryString({ a: null, b: undefined, c: "", d: 1 })).toBe("?d=1");
  });

  it("returns an empty string when nothing is set", () => {
    expect(queryString({ a: null })).toBe("");
  });

  it("preserves explicit false, which is a real value", () => {
    expect(queryString({ is_home: false })).toBe("?is_home=false");
  });

  it("encodes values that would otherwise break the query", () => {
    expect(queryString({ q: "a&b=c" })).toBe("?q=a%26b%3Dc");
  });
});

describe("team endpoints", () => {
  it("scopes the list to one organization", async () => {
    const fetchMock = mockFetch();
    await listTeams("org-1", { limit: 200 });

    const url = urlOf(fetchMock);
    expect(url).toContain("/api/v1/teams");
    expect(url).toContain("organization_id=org-1");
    expect(url).toContain("limit=200");
  });

  it("scopes the detail read, because tenancy is enforced per organization", async () => {
    const fetchMock = mockFetch();
    await getTeam("team-1", "org-1");

    expect(urlOf(fetchMock)).toBe(
      "http://localhost:8000/api/v1/teams/team-1?organization_id=org-1",
    );
  });
});

describe("player endpoints", () => {
  it("passes the squad and date filters", async () => {
    const fetchMock = mockFetch();
    await listPlayers("org-1", { teamId: "team-1", onDate: "2025-09-25" });

    const url = urlOf(fetchMock);
    expect(url).toContain("organization_id=org-1");
    expect(url).toContain("team_id=team-1");
    expect(url).toContain("on_date=2025-09-25");
  });

  it("leaves the optional filters out entirely when unset", async () => {
    const fetchMock = mockFetch();
    await listPlayers("org-1");

    const url = urlOf(fetchMock);
    expect(url).not.toContain("team_id");
    expect(url).not.toContain("on_date");
  });
});

describe("analysis endpoints", () => {
  it("requires a video id, which is why there is no workspace-wide run list", async () => {
    const fetchMock = mockFetch();
    await listAnalysisRuns("video-1");
    expect(urlOf(fetchMock)).toContain("video_id=video-1");
  });
});

describe("user endpoints", () => {
  it("posts the identity fields sign-up collects", async () => {
    const fetchMock = mockFetch();
    await createUser({ email: "alex@example.com", display_name: "Alex Coach" });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/users");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      email: "alex@example.com",
      display_name: "Alex Coach",
    });
  });
});
