"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { apiErrorFor, Field, FormError, SelectField } from "@/components/ui/form";
import { LoadingState } from "@/components/ui/loading-state";
import { useOrganizationId } from "@/features/auth/session";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { useApiQuery } from "@/hooks/use-api-query";
import { createMatch } from "@/services/matches";
import { listTeams } from "@/services/teams";

type SideMode = "team" | "name";

interface SideValue {
  mode: SideMode;
  teamId: string;
  name: string;
}

const EMPTY_SIDE: SideValue = { mode: "name", teamId: "", name: "" };

export function MatchForm() {
  const organizationId = useOrganizationId();
  const router = useRouter();

  const teams = useApiQuery(
    (options) => listTeams(organizationId ?? "", { limit: 200 }, options),
    `teams:${organizationId}`,
    organizationId !== null,
  );

  const [playedOn, setPlayedOn] = useState(() => new Date().toISOString().slice(0, 10));
  const [home, setHome] = useState<SideValue>(EMPTY_SIDE);
  const [away, setAway] = useState<SideValue>(EMPTY_SIDE);
  const [competition, setCompetition] = useState("");
  const [venueName, setVenueName] = useState("");
  const [isHome, setIsHome] = useState(true);

  const { state, mutate } = useApiMutation(createMatch);
  const submitting = state.status === "pending";
  const failure = state.status === "error" ? state.error : null;

  const teamsAvailable = teams.state.status === "success" ? teams.state.data.items : [];
  const homeReady = sideIsIdentified(home);
  const awayReady = sideIsIdentified(away);
  const canSubmit =
    organizationId !== null && playedOn !== "" && homeReady && awayReady && !submitting;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (organizationId === null || !canSubmit) return;

    const created = await mutate({
      organization_id: organizationId,
      played_on: playedOn,
      // Exactly one of id/name per side, so the payload matches what the user chose.
      home_team_id: home.mode === "team" ? home.teamId : null,
      home_team_name: home.mode === "name" ? home.name.trim() : null,
      away_team_id: away.mode === "team" ? away.teamId : null,
      away_team_name: away.mode === "name" ? away.name.trim() : null,
      competition: competition.trim() || null,
      is_home: isHome,
      venue_name: venueName.trim() || null,
    });

    if (created) router.push(`/matches/${encodeURIComponent(created.id)}`);
  }

  return (
    <form className="form" onSubmit={handleSubmit} noValidate>
      {failure ? <FormError error={failure} /> : null}

      <Field
        id="match-date"
        label="Date played"
        type="date"
        required
        hint="The date the fixture took place. Squad membership resolves against it."
        value={playedOn}
        onChange={(event) => setPlayedOn(event.target.value)}
        error={apiErrorFor(failure, "played_on")}
      />

      {teams.state.status === "loading" ? (
        <LoadingState label="Loading your teams" rows={2} />
      ) : teams.state.status === "error" ? (
        <ErrorState
          error={teams.state.error}
          onRetry={teams.reload}
          title="Could not load your teams"
          description="Your teams could not be read, so only free-text side names can be used. You can still create the match."
        />
      ) : null}

      <SideField
        side="home"
        label="Home side"
        value={home}
        onChange={setHome}
        teams={teamsAvailable}
        error={apiErrorFor(failure, "home_team_id") ?? apiErrorFor(failure, "home_team_name")}
      />

      <SideField
        side="away"
        label="Away side"
        value={away}
        onChange={setAway}
        teams={teamsAvailable}
        error={apiErrorFor(failure, "away_team_id") ?? apiErrorFor(failure, "away_team_name")}
      />

      <Field
        id="match-competition"
        label="Competition"
        hint="Optional. The league, cup or friendly series this fixture belongs to."
        value={competition}
        onChange={(event) => setCompetition(event.target.value)}
        error={apiErrorFor(failure, "competition")}
      />

      <Field
        id="match-venue"
        label="Venue"
        hint="Optional. Where the fixture was played."
        value={venueName}
        onChange={(event) => setVenueName(event.target.value)}
        error={apiErrorFor(failure, "venue_name")}
      />

      <SelectField
        id="match-perspective"
        label="Your team`s side"
        hint="From this workspace's point of view — it labels the fixture in lists and reports."
        value={isHome ? "home" : "away"}
        onChange={(value) => setIsHome(value === "home")}
        options={[
          { value: "home", label: "We played at home" },
          { value: "away", label: "We played away" },
        ]}
      />

      <div className="form-actions">
        <Button type="submit" variant="primary" size="md" disabled={!canSubmit}>
          {submitting ? "Creating…" : "Create match"}
        </Button>

        <Button
          type="button"
          variant="technical"
          size="md"
          arrow={false}
          onClick={() => router.back()}
        >
          Cancel
        </Button>
      </div>

      {!homeReady || !awayReady ? (
        <p className="text-caption">
          Both sides must be identified — either from your teams or by name.
        </p>
      ) : null}
    </form>
  );
}

function SideField({
  side,
  label,
  value,
  onChange,
  teams,
  error,
}: {
  side: "home" | "away";
  label: string;
  value: SideValue;
  onChange: (next: SideValue) => void;
  teams: readonly { id: string; name: string }[];
  error: string | undefined;
}) {
  const nameId = `match-${side}-name`;
  const teamId = `match-${side}-team`;

  return (
    <Card>
      <fieldset className="form-field" style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className="form-label">{label}</legend>

        {teams.length > 0 ? (
          <div className="row-wrap" style={{ marginTop: "var(--space-3)" }}>
            <label className="row-center" htmlFor={teamId} style={{ gap: "var(--space-2)" }}>
              <input
                id={teamId}
                type="radio"
                name={`${side}-mode`}
                checked={value.mode === "team"}
                onChange={() => onChange({ ...value, mode: "team" })}
              />
              <span className="text-caption">One of your teams</span>
            </label>

            <label className="row-center" htmlFor={nameId} style={{ gap: "var(--space-2)" }}>
              <input
                id={`${side}-mode-name`}
                type="radio"
                name={`${side}-mode`}
                checked={value.mode === "name"}
                onChange={() => onChange({ ...value, mode: "name" })}
              />
              <span className="text-caption">An opponent by name</span>
            </label>
          </div>
        ) : null}

        {value.mode === "team" && teams.length > 0 ? (
          <div style={{ marginTop: "var(--space-3)" }}>
            <label className="visually-hidden" htmlFor={teamId}>
              {label} team
            </label>
            <select
              id={teamId}
              className="form-control"
              value={value.teamId}
              onChange={(event) => onChange({ ...value, teamId: event.target.value })}
              aria-invalid={error ? true : undefined}
            >
              <option value="">Select a team…</option>
              {teams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.name}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div style={{ marginTop: "var(--space-3)" }}>
            <label className="visually-hidden" htmlFor={nameId}>
              {label} name
            </label>
            <input
              id={nameId}
              className="form-control"
              type="text"
              placeholder="Opponent name"
              value={value.name}
              onChange={(event) => onChange({ ...value, name: event.target.value })}
              aria-invalid={error ? true : undefined}
            />
          </div>
        )}

        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
      </fieldset>
    </Card>
  );
}

/** Whether a side carries enough information for the backend to accept it. */
function sideIsIdentified(side: SideValue): boolean {
  return side.mode === "team" ? side.teamId !== "" : side.name.trim() !== "";
}
