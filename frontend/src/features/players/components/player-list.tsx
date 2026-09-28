"use client";

import { ButtonLink } from "@/components/ui/button";
import { DataCell, DataRow, DataTable } from "@/components/ui/data-table";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/states";
import { useOrganizationId } from "@/features/auth/session";
import { useApiQuery } from "@/hooks/use-api-query";
import { formatAge, formatDate } from "@/lib/format";
import { listPlayers } from "@/services/players";

const MAX_PAGE = 200;

export interface PlayerListProps {
  readonly teamId?: string;
}

export function PlayerList({ teamId }: PlayerListProps) {
  const organizationId = useOrganizationId();

  const { state, reload } = useApiQuery(
    (options) => listPlayers(organizationId ?? "", { teamId, limit: MAX_PAGE }, options),
    `players:${organizationId}:${teamId ?? "all"}`,
    organizationId !== null,
  );

  if (organizationId === null) {
    return (
      <EmptyState
        title="No workspace selected"
        description="Players belong to an organization. Choose a workspace to see its athletes."
      />
    );
  }

  if (state.status === "loading") return <LoadingState label="Loading players" rows={4} />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={reload} />;

  const players = state.data.items;

  if (players.length === 0) {
    return (
      <EmptyState
        icon="motion"
        title={teamId ? "No players in this squad" : "No players yet"}
        description={
          teamId
            ? "No athlete is currently registered to this squad."
            : "Add your first player to start recording who the performance numbers belong to. Players are registered into a squad over time, so a transfer does not rewrite their history."
        }
        actions={
          <ButtonLink href="/players/new" variant="primary" size="md">
            Add player
          </ButtonLink>
        }
      />
    );
  }

  return (
    <div className="stack stack-4">
      <DataTable
        caption="Players in this workspace"
        columns={[
          { id: "name", header: "Player" },
          { id: "age", header: "Age", numeric: true, secondary: true },
          { id: "dob", header: "Date of birth", secondary: true },
          { id: "ref", header: "External ref", secondary: true },
        ]}
      >
        {players.map((player) => (
          <DataRow key={player.id}>
            <DataCell primary>
              <a className="app-row-link" href={`/players/${encodeURIComponent(player.id)}`}>
                {player.display_name}
              </a>
            </DataCell>
            <DataCell numeric secondary>
              {formatAge(player.date_of_birth)}
            </DataCell>
            <DataCell secondary>{formatDate(player.date_of_birth)}</DataCell>
            <DataCell secondary>
              <span className="app-row-meta">{player.external_ref ?? "—"}</span>
            </DataCell>
          </DataRow>
        ))}
      </DataTable>

      <p className="text-caption">
        {players.length === 1 ? "1 player" : `${players.length} players`} in this workspace.
      </p>
    </div>
  );
}
