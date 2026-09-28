"use client";

import { ButtonLink } from "@/components/ui/button";
import { Card, Metric } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PlannedState } from "@/components/ui/states";
import { Tabs } from "@/components/ui/tabs";
import { useOrganizationId } from "@/features/auth/session";
import { useApiQuery } from "@/hooks/use-api-query";
import { formatDate, formatDateTime, formatMatch } from "@/lib/format";
import { listMatches } from "@/services/matches";
import { listPlayers } from "@/services/players";
import { getTeam } from "@/services/teams";
import type { Team } from "@/types/api";

const MAX_PAGE = 200;

export function TeamDetail({ teamId }: { teamId: string }) {
  const organizationId = useOrganizationId();

  const team = useApiQuery(
    (options) => getTeam(teamId, organizationId ?? "", options),
    `team:${organizationId}:${teamId}`,
    organizationId !== null,
  );

  if (organizationId === null) {
    return (
      <PlannedState
        title="No workspace selected"
        description="A team belongs to an organization. Choose a workspace to open it."
      />
    );
  }

  if (team.state.status === "loading") {
    return <LoadingState label="Loading team" rows={4} />;
  }

  if (team.state.status === "error") {
    return <ErrorState error={team.state.error} onRetry={team.reload} />;
  }

  const record = team.state.data;

  return (
    <div className="stack stack-7">
      <TeamSummary team={record} organizationId={organizationId} />

      <Tabs
        label={`${record.name} sections`}
        items={[
          {
            id: "overview",
            label: "Overview",
            content: <TeamOverview team={record} organizationId={organizationId} />,
          },
          {
            id: "players",
            label: "Players",
            content: <TeamPlayers team={record} organizationId={organizationId} />,
          },
          {
            id: "matches",
            label: "Matches",
            content: <TeamMatches team={record} organizationId={organizationId} />,
          },
          {
            id: "videos",
            label: "Videos",
            content: (
              <PlannedState
                title="Videos are not attached to teams"
                description="A recording belongs to a match, and a match belongs to two teams. Video ingestion and processing are not available yet."
                note="Not available yet. This needs video processing."
              />
            ),
          },
          {
            id: "analysis",
            label: "Analysis",
            content: (
              <PlannedState
                title="No analysis for this team yet"
                description="Detection, tracking and movement analysis produce per-player metrics across a season. None of that pipeline is implemented, so there is nothing to show here."
                note="Not available yet. This needs the analysis pipeline."
              />
            ),
          },
        ]}
      />
    </div>
  );
}

function TeamSummary({ team, organizationId }: { team: Team; organizationId: string }) {
  return (
    <div className="detail-grid">
      <div className="stack stack-5">
        <h2 className="heading-subsection">Team information</h2>

        <dl className="fact-list">
          <Fact label="Sport" value={team.sport} />
          <Fact label="Season" value={team.season ?? "Not set"} />
          <Fact label="Short name" value={team.slug} />
          <Fact label="Workspace" value={organizationId} />
          <Fact label="Created" value={formatDateTime(team.created_at)} />
        </dl>
      </div>

      <Card>
        <h2 className="heading-card">Next for this team</h2>
        <p className="text-caption" style={{ marginTop: "var(--space-2)" }}>
          Register players into the squad, then record the fixtures they played. Both are what a
          future analysis run reads from.
        </p>
        <div className="row-wrap" style={{ marginTop: "var(--space-4)" }}>
          <ButtonLink href="/players/new" variant="technical" size="sm">
            Add player
          </ButtonLink>
          <ButtonLink href="/matches/new" variant="technical" size="sm">
            Create match
          </ButtonLink>
        </div>
      </Card>
    </div>
  );
}

function TeamOverview({ team, organizationId }: { team: Team; organizationId: string }) {
  const players = useApiQuery(
    (options) => listPlayers(organizationId, { teamId: team.id, limit: MAX_PAGE }, options),
    `team-players:${organizationId}:${team.id}`,
  );

  const matches = useApiQuery(
    (options) => listMatches(organizationId, { limit: MAX_PAGE }, options),
    `team-matches:${organizationId}`,
  );

  const playersCount = players.state.status === "success" ? players.state.data.meta.count : null;
  const allMatches = matches.state.status === "success" ? matches.state.data.items : null;
  const matchesCount = allMatches
    ? allMatches.filter((item) => involvesTeam(item, team)).length
    : null;

  return (
    <div className="stack stack-6">
      <div className="metric-grid">
        <Metric
          label="Squad size"
          value={playersCount ?? "—"}
          unit={playersCount === 1 ? "player" : "players"}
        />
        <Metric
          label="Matches"
          value={matchesCount ?? "—"}
          unit={matchesCount === 1 ? "fixture" : "fixtures"}
        />
        <Metric label="Videos" value="—" definition="No recordings are attached to a team yet." />
        <Metric
          label="Analysis runs"
          value="—"
          definition="The analysis pipeline is not implemented."
        />
      </div>

      <div className="stack stack-3">
        <h3 className="heading-card">Recent activity</h3>
        <p className="text-caption">
          There is no activity feed in this build. Recording, uploading and analysing all produce
          events that a feed would show, and none of those flows exist yet, so the section is
          deliberately absent rather than filled with a placeholder list.
        </p>
      </div>
    </div>
  );
}

function TeamPlayers({ team, organizationId }: { team: Team; organizationId: string }) {
  const players = useApiQuery(
    (options) => listPlayers(organizationId, { teamId: team.id, limit: MAX_PAGE }, options),
    `team-players:${organizationId}:${team.id}`,
  );

  if (players.state.status === "loading") {
    return <LoadingState label="Loading squad" rows={3} />;
  }

  if (players.state.status === "error") {
    return <ErrorState error={players.state.error} onRetry={players.reload} />;
  }

  if (players.state.data.items.length === 0) {
    return (
      <PlannedState
        title="No players in this squad"
        description="No player is currently registered to this team. Players are added to the organization and then registered into a squad with a validity window, which is what makes a past match`s line-up recoverable after a transfer."
        note="Creating a player and registering squad membership are separate steps."
      />
    );
  }

  return (
    <ul className="ruled-list">
      {players.state.data.items.map((player) => (
        <li key={player.id} className="ruled-item">
          <a className="app-row-link" href={`/players/${encodeURIComponent(player.id)}`}>
            {player.display_name}
          </a>
        </li>
      ))}
    </ul>
  );
}

function TeamMatches({ team, organizationId }: { team: Team; organizationId: string }) {
  const matches = useApiQuery(
    (options) => listMatches(organizationId, { limit: MAX_PAGE }, options),
    `team-matches:${organizationId}`,
  );

  if (matches.state.status === "loading") return <LoadingState label="Loading matches" rows={3} />;
  if (matches.state.status === "error") {
    return <ErrorState error={matches.state.error} onRetry={matches.reload} />;
  }

  const forTeam = matches.state.data.items.filter((item) => involvesTeam(item, team));

  if (forTeam.length === 0) {
    return (
      <PlannedState
        title="No matches for this team"
        description="No fixture in this workspace names this team on either side."
        note="Filtering by team is done in the browser: the matches endpoint has no team filter yet."
      />
    );
  }

  return (
    <ul className="ruled-list">
      {forTeam.map((match) => (
        <li key={match.id} className="ruled-item">
          <a className="app-row-link" href={`/matches/${encodeURIComponent(match.id)}`}>
            {formatMatch(match)}
          </a>
          <span className="text-caption">{formatDate(match.played_on)}</span>
        </li>
      ))}
    </ul>
  );
}

function involvesTeam(
  match: { home_team_id: string | null; away_team_id: string | null },
  team: Team,
): boolean {
  return match.home_team_id === team.id || match.away_team_id === team.id;
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="fact">
      <dt className="fact-label">{label}</dt>
      <dd className="fact-value">{value}</dd>
    </div>
  );
}
