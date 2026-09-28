"use client";

import Link from "next/link";

import { Container } from "@/components/ui/section";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PlannedState } from "@/components/ui/states";
import { useOrganizationId, useSession } from "@/features/auth/session";
import { useApiQuery } from "@/hooks/use-api-query";
import { listMatches } from "@/services/matches";
import { listPlayers } from "@/services/players";
import { listTeams } from "@/services/teams";
import { listVideos } from "@/services/videos";

const MAX_PAGE = 200;

export function DashboardOverview() {
  const organizationId = useOrganizationId();
  const { organization } = useSession();

  const teams = useApiQuery(
    (options) => listTeams(organizationId ?? "", { limit: MAX_PAGE }, options),
    `teams:${organizationId}`,
    organizationId !== null,
  );

  const players = useApiQuery(
    (options) => listPlayers(organizationId ?? "", { limit: MAX_PAGE }, options),
    `players:${organizationId}`,
    organizationId !== null,
  );

  const matches = useApiQuery(
    (options) => listMatches(organizationId ?? "", { limit: MAX_PAGE }, options),
    `matches:${organizationId}`,
    organizationId !== null,
  );

  const videos = useApiQuery(
    (options) => listVideos(organizationId ?? "", { limit: MAX_PAGE }, options),
    `videos:${organizationId}`,
    organizationId !== null,
  );

  if (organizationId === null) {
    return (
      <PlannedState
        title="No workspace selected"
        description="The dashboard summarises one organization at a time. Choose a workspace from the header to see its teams, players, matches and videos."
      />
    );
  }

  const queries = [teams, players, matches, videos];
  const anyLoading = queries.some((query) => query.state.status === "loading");
  const firstError = queries.find((query) => query.state.status === "error");

  if (anyLoading && firstError === undefined) {
    return <LoadingState label="Loading workspace summary" rows={3} />;
  }

  if (firstError && firstError.state.status === "error") {
    return <ErrorState error={firstError.state.error} onRetry={reloadAll(queries)} />;
  }

  const count = (state: (typeof queries)[number]["state"]) =>
    state.status === "success" ? state.data.meta.count : 0;

  const teamsCount = count(teams.state);
  const playersCount = count(players.state);
  const matchesCount = count(matches.state);
  const videosCount = count(videos.state);

  const workspaceIsEmpty =
    teamsCount === 0 && playersCount === 0 && matchesCount === 0 && videosCount === 0;

  return (
    <div className="stack stack-8">
      <section aria-labelledby="overview-heading" className="stack stack-5">
        <h2 id="overview-heading" className="heading-subsection">
          Overview
        </h2>

        <ul className="overview-grid">
          <OverviewTile
            href="/teams"
            label="Teams"
            value={teams.state.status === "success" ? teamsCount : null}
            meta={scopeNote(teams.state.status === "success" ? teamsCount : null, "squad")}
          />
          <OverviewTile
            href="/players"
            label="Players"
            value={players.state.status === "success" ? playersCount : null}
            meta={scopeNote(players.state.status === "success" ? playersCount : null, "player")}
          />
          <OverviewTile
            href="/matches"
            label="Matches"
            value={matches.state.status === "success" ? matchesCount : null}
            meta={scopeNote(matches.state.status === "success" ? matchesCount : null, "fixture")}
          />
          <OverviewTile
            href="/videos"
            label="Videos"
            value={videos.state.status === "success" ? videosCount : null}
            meta={scopeNote(videos.state.status === "success" ? videosCount : null, "recording")}
          />
          <OverviewTile href="/analysis" label="Analyses" value={null} meta="Not available" />
        </ul>

        <p className="text-caption">
          Counts are read live from the {organization?.name ?? "workspace"} workspace. Analyses are
          listed per video, so a workspace-wide total is not available yet.
        </p>
      </section>

      {workspaceIsEmpty ? (
        <section aria-labelledby="onboarding-heading">
          <Container width="page">
            <div className="stack stack-5">
              <div className="stack stack-2">
                <h2 id="onboarding-heading" className="heading-section">
                  Build your performance workspace
                </h2>
                <p className="text-body">
                  A workspace is a team of players and a record of their matches. Each step below is
                  the next thing to do, in the order the product needs it.
                </p>
              </div>

              <ol className="step-list">
                <OnboardingStep
                  index="01"
                  label="Create a team"
                  detail="A squad, with the sport it plays and the season it belongs to."
                  href="/teams/new"
                  actionLabel="Create a team"
                />
                <OnboardingStep
                  index="02"
                  label="Add players"
                  detail="Players belong to the organization and are registered into a squad, so a transfer does not rewrite their history."
                  href="/players/new"
                  actionLabel="Add a player"
                />
                <OnboardingStep
                  index="03"
                  label="Create a match"
                  detail="A fixture is what videos, analysis runs and reports hang off."
                  href="/matches/new"
                  actionLabel="Create a match"
                />
                <OnboardingStep
                  index="04"
                  label="Add video"
                  detail="Match recordings live in the video library."
                  href="/videos"
                  actionLabel="Go to videos"
                />
                <OnboardingStep
                  index="05"
                  label="Analyse performance"
                  detail="Analysis runs are queued against a video. The processing pipeline is not available yet."
                  href="/analysis"
                  actionLabel="Go to analysis"
                />
              </ol>
            </div>
          </Container>
        </section>
      ) : null}
    </div>
  );
}

function OverviewTile({
  href,
  label,
  value,
  meta,
}: {
  href: string;
  label: string;
  value: number | null;
  meta: string;
}) {
  return (
    <li>
      <Link href={href} className="overview-tile">
        <span className="overview-tile-label">{label}</span>
        <span className="overview-tile-value">{value ?? "—"}</span>
        <span className="overview-tile-meta">{meta}</span>
      </Link>
    </li>
  );
}

function scopeNote(value: number | null, noun: string): string {
  if (value === null) return "Not available";
  if (value === 0) return `No ${noun}s yet`;
  if (value >= MAX_PAGE) return `${MAX_PAGE}+ — count capped by page size`;
  return value === 1 ? `1 ${noun}` : `${value} ${noun}s`;
}

function OnboardingStep({
  index,
  label,
  detail,
  href,
  actionLabel,
}: {
  index: string;
  label: string;
  detail: string;
  href: string;
  actionLabel: string;
}) {
  return (
    <li className="step">
      <span className="step-index" aria-hidden="true">
        {index}
      </span>
      <span className="step-label">{label}</span>
      <span className="step-detail">
        {detail}{" "}
        <Link href={href} className="app-row-link">
          {actionLabel}
        </Link>
      </span>
    </li>
  );
}

function reloadAll(queries: readonly { reload: () => void }[]): () => void {
  return () => {
    for (const query of queries) query.reload();
  };
}
