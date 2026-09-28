"use client";

import { Metric } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PlannedState, StateBlock } from "@/components/ui/states";
import { useOrganizationId } from "@/features/auth/session";
import { useApiQuery } from "@/hooks/use-api-query";
import { formatAge, formatDate, formatDateTime } from "@/lib/format";
import { getPlayer } from "@/services/players";

export function PlayerDetail({ playerId }: { playerId: string }) {
  const organizationId = useOrganizationId();

  const player = useApiQuery(
    (options) => getPlayer(playerId, organizationId ?? "", options),
    `player:${organizationId}:${playerId}`,
    organizationId !== null,
  );

  if (organizationId === null) {
    return (
      <PlannedState
        title="No workspace selected"
        description="A player belongs to an organization. Choose a workspace to open this profile."
      />
    );
  }

  if (player.state.status === "loading") return <LoadingState label="Loading player" rows={4} />;
  if (player.state.status === "error") {
    return <ErrorState error={player.state.error} onRetry={player.reload} />;
  }

  const record = player.state.data;

  return (
    <div className="stack stack-7">
      <section aria-labelledby="player-profile-heading" className="detail-grid">
        <div className="stack stack-5">
          <h2 id="player-profile-heading" className="heading-subsection">
            Profile
          </h2>

          <dl className="fact-list">
            <Fact label="Name" value={record.display_name} />
            <Fact label="Date of birth" value={formatDate(record.date_of_birth)} />
            <Fact label="Age" value={formatAge(record.date_of_birth)} />
            <Fact label="External reference" value={record.external_ref ?? "Not set"} />
            <Fact label="Added" value={formatDateTime(record.created_at)} />
          </dl>
        </div>

        <div className="stack stack-4">
          <Metric
            label="Matches recorded"
            value="—"
            definition="No per-player match participation is modelled yet."
          />
          <Metric
            label="Performance metrics"
            value="—"
            definition="Distance, speed and workload require the analysis pipeline."
          />
        </div>
      </section>

      <section aria-labelledby="player-team-heading" className="stack stack-4">
        <h2 id="player-team-heading" className="heading-subsection">
          Team
        </h2>
        <PlayerTeam />
      </section>

      <section aria-labelledby="player-future-heading" className="stack stack-4">
        <h2 id="player-future-heading" className="heading-subsection">
          Matches · Videos · Analysis · Reports
        </h2>

        <StateBlock
          tone="placeholder"
          title="Not yet available for a player"
          description={
            <>
              <p>
                Matches, videos, analysis runs and reports are all modelled against a match or a
                video, not against a player, so there is nothing to link to from here yet. Each row
                below names what will fill it.
              </p>
              <ul className="document-list" style={{ marginTop: "var(--space-4)" }}>
                <li className="document-list-item">
                  Matches — the fixtures this player appeared in.
                </li>
                <li className="document-list-item">
                  Videos — recordings in which the player is tracked.
                </li>
                <li className="document-list-item">
                  Analysis — per-player runs, once tracking produces identities.
                </li>
                <li className="document-list-item">
                  Reports — player reports generated from those runs.
                </li>
              </ul>
            </>
          }
        />
      </section>
    </div>
  );
}

function PlayerTeam() {
  return (
    <PlannedState
      title="Squad membership is not resolvable from this page"
      description="Squad registration is stored as a dated membership, and there is no endpoint that lists a player's memberships. Reading it is one request per team, which is why this is deferred rather than guessed."
      note="Not available yet. This needs a memberships endpoint, or a filter on squad resolution."
    />
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="fact">
      <dt className="fact-label">{label}</dt>
      <dd className="fact-value">{value}</dd>
    </div>
  );
}
