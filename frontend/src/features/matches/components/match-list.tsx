"use client";

import { ButtonLink } from "@/components/ui/button";
import { DataCell, DataRow, DataTable } from "@/components/ui/data-table";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/states";
import { useOrganizationId } from "@/features/auth/session";
import { useApiQuery } from "@/hooks/use-api-query";
import { formatDate, formatMatch } from "@/lib/format";
import { listMatches } from "@/services/matches";

const MAX_PAGE = 200;

export function MatchList() {
  const organizationId = useOrganizationId();

  const { state, reload } = useApiQuery(
    (options) => listMatches(organizationId ?? "", { limit: MAX_PAGE }, options),
    `matches:${organizationId}`,
    organizationId !== null,
  );

  if (organizationId === null) {
    return (
      <EmptyState
        title="No workspace selected"
        description="Matches belong to an organization. Choose a workspace to see its fixtures."
      />
    );
  }

  if (state.status === "loading") return <LoadingState label="Loading matches" rows={4} />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={reload} />;

  const matches = state.data.items;

  if (matches.length === 0) {
    return (
      <EmptyState
        title="No matches yet"
        description="Create your first match to give video and analysis somewhere to attach. A fixture names the two sides, the date and — once the analysis pipeline exists — the recordings and results that hang off it."
        actions={
          <ButtonLink href="/matches/new" variant="primary" size="md">
            Create match
          </ButtonLink>
        }
      />
    );
  }

  return (
    <div className="stack stack-4">
      <DataTable
        caption="Matches in this workspace"
        columns={[
          { id: "fixture", header: "Fixture" },
          { id: "date", header: "Date" },
          { id: "competition", header: "Competition", secondary: true },
          { id: "venue", header: "Venue", secondary: true },
          { id: "sides", header: "Home / away", secondary: true },
        ]}
      >
        {matches.map((match) => (
          <DataRow key={match.id}>
            <DataCell primary>
              <a className="app-row-link" href={`/matches/${encodeURIComponent(match.id)}`}>
                {formatMatch(match)}
              </a>
            </DataCell>
            <DataCell>{formatDate(match.played_on)}</DataCell>
            <DataCell secondary>{match.competition ?? "—"}</DataCell>
            <DataCell secondary>{match.venue_name ?? "—"}</DataCell>
            <DataCell secondary>
              {/* `is_home' is from the workspace's own perspective, which is the only
                  side the domain can be sure about. */}
              <span className="app-row-meta">{match.is_home ? "Home" : "Away"}</span>
            </DataCell>
          </DataRow>
        ))}
      </DataTable>

      <p className="text-caption">
        {matches.length === 1 ? "1 match" : `${matches.length} matches`} in this workspace. Results
        and scores are not recorded: the backend has no score model.
      </p>
    </div>
  );
}
