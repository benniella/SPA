"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { apiErrorFor, Field, FormError } from "@/components/ui/form";
import { useOrganizationId } from "@/features/auth/session";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { createTeam } from "@/services/teams";
import { ApiError } from "@/lib/api-errors";

export interface TeamFormProps {
  readonly onCreated?: (teamId: string) => void;
}

export function TeamForm({ onCreated }: TeamFormProps) {
  const organizationId = useOrganizationId();
  const router = useRouter();

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [sport, setSport] = useState("football");
  const [season, setSeason] = useState("");

  const { state, mutate } = useApiMutation(createTeam);
  const submitting = state.status === "pending";
  const failure = state.status === "error" ? state.error : null;

  const effectiveSlug = slugTouched ? slug : slugify(name);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (organizationId === null) return;

    const created = await mutate({
      organization_id: organizationId,
      name: name.trim(),
      slug: effectiveSlug,
      sport: sport.trim() || "football",
      season: season.trim() || null,
    });

    if (created) {
      if (onCreated) onCreated(created.id);
      else router.push(`/teams/${encodeURIComponent(created.id)}`);
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit} noValidate>
      {failure ? <FormError error={failure} /> : null}

      <Field
        id="team-name"
        label="Team name"
        required
        hint="As it will appear across the workspace, for example “Riverside First Team”."
        value={name}
        onChange={(event) => setName(event.target.value)}
        error={apiErrorFor(failure, "name")}
      />

      <Field
        id="team-slug"
        label="Short name"
        required
        hint="Used in URLs and reports. Lowercase letters, numbers and single hyphens."
        value={effectiveSlug}
        onChange={(event) => {
          setSlugTouched(true);
          setSlug(event.target.value);
        }}
        error={apiErrorFor(failure, "slug")}
      />

      <Field
        id="team-sport"
        label="Sport"
        hint="Football is the sport SPA models today; others are planned."
        value={sport}
        onChange={(event) => setSport(event.target.value)}
        error={apiErrorFor(failure, "sport")}
      />

      <Field
        id="team-season"
        label="Season"
        hint="Optional. A label such as “2025/26”, so squads can be compared across years."
        value={season}
        onChange={(event) => setSeason(event.target.value)}
        error={apiErrorFor(failure, "season")}
      />

      <div className="form-actions">
        <Button
          type="submit"
          variant="primary"
          size="md"
          disabled={submitting || organizationId === null || name.trim() === ""}
          onClick={undefined}
        >
          {submitting ? "Creating…" : "Create team"}
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

      {organizationId === null ? (
        <p className="text-caption">
          A team belongs to an organization. Choose a workspace before creating one.
        </p>
      ) : null}
    </form>
  );
}

export function slugify(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

export { apiErrorFor as teamFieldError, ApiError as TeamApiError };
