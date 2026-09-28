import Link from "next/link";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorState } from "@/components/ui/error-state";
import { describeError } from "@/components/ui/error-copy";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState, PlannedState } from "@/components/ui/states";
import { ApiError, NetworkError } from "@/lib/api-errors";

describe("EmptyState", () => {
  it("states what is empty, why it matters and what to do", () => {
    render(
      <EmptyState
        title="No teams yet"
        description="Create your first team to start building your performance workspace."
        actions={<Link href="/teams/new">Create team</Link>}
      />,
    );

    expect(screen.getByRole("heading", { name: "No teams yet" })).toBeInTheDocument();
    expect(screen.getByText(/start building your performance workspace/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create team" })).toBeInTheDocument();
  });

  it("is announced as an empty state rather than as a generic region", () => {
    render(<EmptyState title="No teams yet" description="Nothing here." />);
    expect(screen.getByRole("region", { name: "Nothing here yet" })).toBeInTheDocument();
  });
});

describe("PlannedState", () => {
  it("is distinguishable from empty and names what would unblock it", () => {
    render(
      <PlannedState
        title="Analysis is not implemented"
        description="The pipeline does not exist."
        note="Not available yet. This needs analysis."
      />,
    );

    expect(screen.getByRole("region", { name: "Not available yet" })).toBeInTheDocument();
    expect(screen.getByText("Not available yet. This needs analysis.")).toBeInTheDocument();
  });
});

describe("LoadingState", () => {
  it("announces itself politely and names what is loading", () => {
    render(<LoadingState label="Loading teams" rows={3} />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(screen.getByText("Loading teams")).toBeInTheDocument();
  });

  it("hides the decorative skeleton from assistive technology", () => {
    const { container } = render(<LoadingState label="Loading teams" rows={2} />);
    const rows = container.querySelectorAll(".skeleton-row");
    expect(rows.length).toBe(2);
    expect(rows[0]?.parentElement).toHaveAttribute("aria-hidden", "true");
  });
});

describe("describeError", () => {
  it("does not expose a raw backend message for a not-found", () => {
    const copy = describeError(new ApiError(404, "not_found", "Video 4e4eb065 does not exist."));

    expect(copy.title).toBe("Not found");
    expect(copy.description).not.toContain("4e4eb065");
    expect(copy.retryable).toBe(false);
  });

  it("treats an unreachable API as retryable and says so plainly", () => {
    const copy = describeError(new NetworkError("Could not reach the SPA API."));

    expect(copy.title).toBe("Could not reach SPA");
    expect(copy.retryable).toBe(true);
  });

  it("switches on the code, not the message", () => {
    const reworded = new ApiError(503, "infrastructure_error", "Nginx upstream timed out");
    const copy = describeError(reworded);

    expect(copy.retryable).toBe(true);
    expect(copy.description).not.toContain("Nginx");
  });

  it("routes an unauthenticated failure to sign-in", () => {
    const copy = describeError(new ApiError(401, "authentication_required", "Not authenticated."));
    expect(copy.needsSignIn).toBe(true);
  });

  it("does not leak infrastructure detail for an internal error", () => {
    const copy = describeError(
      new ApiError(500, "internal_error", "psycopg.OperationalError: connection refused"),
    );

    expect(copy.description).not.toMatch(/psycopg|connection refused|OperationalError/);
  });
});

describe("ErrorState", () => {
  it("offers retry only when retrying could help", () => {
    const onRetry = vi.fn();

    const { unmount } = render(
      <ErrorState error={new ApiError(404, "not_found", "Gone.")} onRetry={onRetry} />,
    );
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
    unmount();

    render(
      <ErrorState error={new ApiError(503, "infrastructure_error", "Down.")} onRetry={onRetry} />,
    );
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("offers sign-in when the session has ended", () => {
    render(
      <ErrorState error={new ApiError(401, "authentication_required", "Not authenticated.")} />,
    );

    expect(screen.getByRole("link", { name: "Go to sign in" })).toHaveAttribute("href", "/sign-in");
  });
});
