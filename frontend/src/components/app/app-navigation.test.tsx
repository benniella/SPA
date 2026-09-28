import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppMobileNav, AppSidebar } from "@/components/app/app-navigation";
import { RequireSession } from "@/features/auth";
import { SessionProvider } from "@/features/auth/session";
import type { Organization } from "@/types/api";

const replace = vi.fn();
let pathname = "/dashboard";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ replace, push: vi.fn(), back: vi.fn() }),
}));

const ORGANIZATION: Organization = {
  id: "org-1",
  name: "Riverside FC",
  slug: "riverside-fc",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

function stubApi(routes: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      for (const [path, payload] of Object.entries(routes)) {
        if (url.includes(path)) {
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
        json: async () => ({ error: { code: "not_found", message: "No route." } }),
      } as Response;
    }),
  );
}

const organizationsPage = {
  items: [ORGANIZATION],
  meta: { limit: 50, offset: 0, count: 1 },
};

beforeEach(() => {
  replace.mockClear();
  pathname = "/dashboard";
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
});

describe("AppSidebar", () => {
  it("lists every application destination", () => {
    stubApi({ "/organizations": organizationsPage });
    render(
      <SessionProvider>
        <AppSidebar />
      </SessionProvider>,
    );

    for (const label of [
      "Dashboard",
      "Teams",
      "Players",
      "Matches",
      "Videos",
      "Analysis",
      "Reports",
      "Settings",
      "Account",
    ]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
  });

  it("marks the active route for assistive technology, not only visually", () => {
    stubApi({ "/organizations": organizationsPage });
    pathname = "/teams";

    render(
      <SessionProvider>
        <AppSidebar />
      </SessionProvider>,
    );

    expect(screen.getByRole("link", { name: "Teams" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Players" })).not.toHaveAttribute("aria-current");
  });

  it("keeps a section marked on a nested detail route", () => {
    stubApi({ "/organizations": organizationsPage });
    pathname = "/teams/abc-123";

    render(
      <SessionProvider>
        <AppSidebar />
      </SessionProvider>,
    );

    expect(screen.getByRole("link", { name: "Teams" })).toHaveAttribute("aria-current", "page");
  });

  it("exposes the collapse control as an expandable button", () => {
    stubApi({ "/organizations": organizationsPage });
    render(
      <SessionProvider>
        <AppSidebar />
      </SessionProvider>,
    );

    expect(screen.getByRole("button", { name: "Collapse navigation" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });
});

describe("AppMobileNav", () => {
  it("is a labelled navigation landmark", () => {
    stubApi({ "/organizations": organizationsPage });
    render(
      <SessionProvider>
        <AppMobileNav />
      </SessionProvider>,
    );

    expect(screen.getByRole("navigation", { name: "Application" })).toBeInTheDocument();
  });

  it("keeps the secondary destinations reachable behind More", async () => {
    stubApi({ "/organizations": organizationsPage });
    render(
      <SessionProvider>
        <AppMobileNav />
      </SessionProvider>,
    );

    const more = screen.getByRole("button", { name: "More" });
    expect(more).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(more);

    await waitFor(() => expect(more).toHaveAttribute("aria-expanded", "true"));
    expect(screen.getByRole("button", { name: "Close navigation" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Account" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Analysis" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close navigation" }));
    await waitFor(() => expect(more).toHaveAttribute("aria-expanded", "false"));
  });
});

describe("RequireSession", () => {
  it("does not render protected content while the session is unresolved", () => {
    stubApi({ "/organizations": organizationsPage });

    render(
      <SessionProvider>
        <RequireSession from="/dashboard">
          <p>Protected dashboard content</p>
        </RequireSession>
      </SessionProvider>,
    );

    expect(screen.queryByText("Protected dashboard content")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("redirects rather than rendering when there is no session", async () => {
    stubApi({ "/organizations": organizationsPage });

    render(
      <SessionProvider>
        <RequireSession from="/dashboard">
          <p>Protected dashboard content</p>
        </RequireSession>
      </SessionProvider>,
    );

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/sign-in?from=%2Fdashboard"));
    expect(screen.queryByText("Protected dashboard content")).not.toBeInTheDocument();
  });

  it("renders the application once a workspace is selected", async () => {
    stubApi({ "/organizations": organizationsPage });
    window.localStorage.setItem("spa.dev.workspace", ORGANIZATION.id);

    render(
      <SessionProvider>
        <RequireSession from="/dashboard">
          <p>Protected dashboard content</p>
        </RequireSession>
      </SessionProvider>,
    );

    await waitFor(() =>
      expect(screen.getByText("Protected dashboard content")).toBeInTheDocument(),
    );
    expect(replace).not.toHaveBeenCalled();
  });

  it("treats a stored workspace that no longer exists as unauthenticated", async () => {
    stubApi({ "/organizations": organizationsPage });
    window.localStorage.setItem("spa.dev.workspace", "org-does-not-exist");

    render(
      <SessionProvider>
        <RequireSession from="/teams">
          <p>Protected content</p>
        </RequireSession>
      </SessionProvider>,
    );

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/sign-in?from=%2Fteams"));
    expect(window.localStorage.getItem("spa.dev.workspace")).toBeNull();
  });

  it("does not redirect to a non-application path from the from parameter", () => {
    stubApi({ "/organizations": organizationsPage });

    render(
      <SessionProvider>
        <RequireSession from="/marketing-page">
          <p>Protected content</p>
        </RequireSession>
      </SessionProvider>,
    );

    expect(replace).not.toHaveBeenCalledWith("/sign-in?from=%2Fmarketing-page");
  });
});
