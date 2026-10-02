import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionProvider } from "@/features/auth/session";
import { MatchList } from "@/features/matches";
import { PlayerList } from "@/features/players";
import { TeamList } from "@/features/teams";
import type { AuthenticatedUser, Organization } from "@/types/api";
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
function stubApi(routes: Record<string, unknown>) {
  /* The session provider resolves '/auth/me' on mount, so every page under test
     needs that route whether or not the test is about authentication. */
  const allRoutes: Record<string, unknown> = { "/auth/me": ACCOUNT, ...routes };
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input)).pathname;
    for (const [route, payload] of Object.entries(allRoutes)) {
      if (path === `/api/v1${route}`) {
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
      json: async () => ({
        error: { code: "not_found", message: `No stub route for ${path}.` },
      }),
    } as Response;
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function withSession(children: React.ReactNode) {
  window.localStorage.setItem("spa.workspace", ORGANIZATION.id);
  return render(<SessionProvider>{children}</SessionProvider>);
}

async function settled(assertion: () => void) {
  await waitFor(assertion);
}

function page<T>(items: T[]) {
  return { items, meta: { limit: 200, offset: 0, count: items.length } };
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
});

describe("TeamList", () => {
  it("shows a loading state once the workspace is known and the teams request is in flight", () => {
    stubApi({ "/organizations": page([ORGANIZATION]), "/teams": page([]) });
    withSession(<TeamList />);

    expect(screen.getByRole("region", { name: "Nothing here yet" })).toBeInTheDocument();
  });

  it("invites the reader to create the first team when the list is empty", async () => {
    stubApi({ "/organizations": page([ORGANIZATION]), "/teams": page([]) });
    withSession(<TeamList />);

    await settled(() =>
      expect(screen.getByRole("heading", { name: "No teams yet" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("link", { name: "Create team" })).toHaveAttribute("href", "/teams/new");
  });

  it("renders real teams and links each to its detail page", async () => {
    stubApi({
      "/organizations": page([ORGANIZATION]),
      "/teams": page([
        {
          id: "team-1",
          organization_id: ORGANIZATION.id,
          name: "First Team",
          slug: "first-team",
          sport: "football",
          season: "2025/26",
          created_at: "2025-01-01T00:00:00Z",
          updated_at: "2025-01-01T00:00:00Z",
        },
      ]),
    });

    withSession(<TeamList />);

    await waitFor(() => expect(screen.getByText("First Team")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "First Team" })).toHaveAttribute(
      "href",
      "/teams/team-1",
    );
    expect(screen.getByRole("table", { name: /teams in this workspace/i })).toBeInTheDocument();
  });

  it("shows the error state when the request fails", async () => {
    stubApi({ "/organizations": page([ORGANIZATION]) });
    withSession(<TeamList />);

    await waitFor(() =>
      expect(screen.getByRole("region", { name: /went wrong/i })).toBeInTheDocument(),
    );
  });
});

describe("PlayerList", () => {
  it("uses language about athletes rather than generic records", async () => {
    stubApi({ "/organizations": page([ORGANIZATION]), "/players": page([]) });
    withSession(<PlayerList />);

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "No players yet" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("link", { name: "Add player" })).toHaveAttribute(
      "href",
      "/players/new",
    );
  });

  it("renders a player without inventing a date of birth", async () => {
    stubApi({
      "/organizations": page([ORGANIZATION]),
      "/players": page([
        {
          id: "player-1",
          organization_id: ORGANIZATION.id,
          display_name: "Alex Morgan",
          date_of_birth: null,
          external_ref: null,
          created_at: "2025-01-01T00:00:00Z",
          updated_at: "2025-01-01T00:00:00Z",
        },
      ]),
    });

    withSession(<PlayerList />);

    await waitFor(() => expect(screen.getByText("Alex Morgan")).toBeInTheDocument());
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});

describe("MatchList", () => {
  it("states that results are not modelled rather than showing a score", async () => {
    stubApi({
      "/organizations": page([ORGANIZATION]),
      "/matches": page([
        {
          id: "match-1",
          organization_id: ORGANIZATION.id,
          played_on: "2025-09-01",
          home_team_id: null,
          away_team_id: null,
          home_team_name: "Riverside",
          away_team_name: "Hilltop",
          competition: "League",
          is_home: true,
          venue_name: null,
          created_at: "2025-09-01T00:00:00Z",
          updated_at: "2025-09-01T00:00:00Z",
        },
      ]),
    });

    withSession(<MatchList />);

    await waitFor(() => expect(screen.getByText("Riverside vs Hilltop")).toBeInTheDocument());
    expect(screen.getByText(/results and scores are not recorded/i)).toBeInTheDocument();
  });

  it("offers the create action when there are no fixtures", async () => {
    stubApi({ "/organizations": page([ORGANIZATION]), "/matches": page([]) });
    withSession(<MatchList />);

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "No matches yet" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("link", { name: "Create match" })).toHaveAttribute(
      "href",
      "/matches/new",
    );
  });
});
