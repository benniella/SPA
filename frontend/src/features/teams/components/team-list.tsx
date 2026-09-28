"use client";

import { ButtonLink } from "@/components/ui/button";
import { DataCell, DataRow, DataTable } from "@/components/ui/data-table";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/states";
import { useOrganizationId } from "@/features/auth/session";
import { useApiQuery } from "@/hooks/use-api-query";
import { listTeams } from "@/services/teams";

const MAX_PAGE = 200;

export interface TeamListProps {
  readonly organizationId?: string | null;
  readonly scopeLabel?: string;
}

export function TeamList({ organizationId, scopeLabel }: TeamListProps) {
  const sessionOrganizationId = useOrganizationId();
  const activeId = organizationId === undefined ? sessionOrganizationId : organizationId;

  const { state, reload } = useApiQuery(
    (options) => listTeams(activeId ?? "", { limit: MAX_PAGE }, options),
    `teams:${activeId}`,
    activeId !== null,
  );

  if (activeId === null) {
    return (
      <EmptyState
        title="No workspace selected"
        description="Teams belong to an organization. Choose a workspace to see the squads it manages."
        actions={
          <ButtonLink href="/settings" variant="technical" size="md">
            Choose a workspace
          </ButtonLink>
        }
      />
    );
  }

  if (state.status === "loading") {
    return <LoadingState label="Loading teams" rows={4} />;
  }

  if (state.status === "error") {
    return <ErrorState error={state.error} onRetry={reload} />;
  }

  const teams = state.data.items;

  if (teams.length === 0) {
    return (
      <EmptyState
        icon="sport"
        title="No teams yet"
        description={
          scopeLabel
            ? "This workspace has no squad registered. Create a team to start building the performance workspace around it."
            : "Create your first team to start building your performance workspace. A team is the squad whose players and matches everything else is organised around."
        }
        actions={
          <ButtonLink href="/teams/new" variant="primary" size="md">
            Create team
          </ButtonLink>
        }
      />
    );
  }

  return (
    <div className="stack stack-4">
      <DataTable
        caption="Teams in this workspace"
        columns={[
          { id: "name", header: "Team" },
          { id: "sport", header: "Sport" },
          { id: "season", header: "Season", secondary: true },
          { id: "slug", header: "Short name", secondary: true },
        ]}
      >
        {teams.map((team) => (
          <DataRow key={team.id}>
            <DataCell primary>
              <TeamLink id={team.id} name={team.name} />
            </DataCell>
            <DataCell>{team.sport}</DataCell>
            <DataCell secondary>{team.season ?? "—"}</DataCell>
            <DataCell secondary>
              <span className="app-row-meta">{team.slug}</span>
            </DataCell>
          </DataRow>
        ))}
      </DataTable>

      <p className="text-caption">
        {teams.length === 1 ? "1 team" : `${teams.length} teams`} in this workspace.
      </p>
    </div>
  );
}

export function TeamLink({ id, name }: { id: string; name: string }) {
  return (
    <a className="app-row-link" href={`/teams/${encodeURIComponent(id)}`}>
      {name}
    </a>
  );
}
