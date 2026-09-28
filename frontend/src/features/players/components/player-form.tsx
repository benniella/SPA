"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { apiErrorFor, Field, FormError } from "@/components/ui/form";
import { useOrganizationId } from "@/features/auth/session";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { createPlayer } from "@/services/players";

export function PlayerForm() {
  const organizationId = useOrganizationId();
  const router = useRouter();

  const [displayName, setDisplayName] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [externalRef, setExternalRef] = useState("");

  const { state, mutate } = useApiMutation(createPlayer);
  const submitting = state.status === "pending";
  const failure = state.status === "error" ? state.error : null;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (organizationId === null) return;

    const created = await mutate({
      organization_id: organizationId,
      display_name: displayName.trim(),
      date_of_birth: dateOfBirth || null,
      external_ref: externalRef.trim() || null,
    });

    if (created) router.push(`/players/${encodeURIComponent(created.id)}`);
  }

  return (
    <form className="form" onSubmit={handleSubmit} noValidate>
      {failure ? <FormError error={failure} /> : null}

      <Field
        id="player-name"
        label="Display name"
        required
        hint="The name shown across the workspace."
        value={displayName}
        onChange={(event) => setDisplayName(event.target.value)}
        error={apiErrorFor(failure, "display_name")}
      />

      <Field
        id="player-dob"
        label="Date of birth"
        type="date"
        hint="Optional. Used for age, and for age-group reporting in academies."
        value={dateOfBirth}
        onChange={(event) => setDateOfBirth(event.target.value)}
        error={apiErrorFor(failure, "date_of_birth")}
      />

      <Field
        id="player-ref"
        label="External reference"
        hint="Optional. An id from an existing squad-management system, so records can be reconciled."
        value={externalRef}
        onChange={(event) => setExternalRef(event.target.value)}
        error={apiErrorFor(failure, "external_ref")}
      />

      <div className="form-actions">
        <Button
          type="submit"
          variant="primary"
          size="md"
          disabled={submitting || organizationId === null || displayName.trim() === ""}
        >
          {submitting ? "Adding…" : "Add player"}
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
          A player belongs to an organization. Choose a workspace before adding one.
        </p>
      ) : null}
    </form>
  );
}
