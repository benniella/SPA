"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiErrorFor, Field, FormError } from "@/components/ui/form";
import { LoadingState } from "@/components/ui/loading-state";
import { PlannedState } from "@/components/ui/states";
import { slugify } from "@/features/teams";
import { useSession } from "@/features/auth/session";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { createOrganization } from "@/services/organizations";
import type { Organization } from "@/types/api";

export function WorkspaceSettings() {
  const { status, organization, organizations, selectWorkspace, refresh } = useSession();

  if (status === "loading") {
    return <LoadingState label="Loading workspaces" rows={3} />;
  }

  return (
    <div className="stack stack-7">
      <section aria-labelledby="current-workspace-heading" className="stack stack-4">
        <h2 id="current-workspace-heading" className="heading-subsection">
          Current workspace
        </h2>

        {organization ? (
          <Card>
            <dl className="fact-list">
              <Fact label="Name" value={organization.name} />
              <Fact label="Short name" value={organization.slug} />
              <Fact label="Your role" value={organization.role} />
            </dl>
          </Card>
        ) : (
          <PlannedState
            title="No workspace selected"
            description="Every team, player, match and video belongs to an organization, so the application needs one before it can show anything. Create one below."
          />
        )}

        {organizations.length > 1 ? (
          <div className="stack stack-3">
            <h3 className="heading-card">Switch workspace</h3>
            <p className="text-caption">
              You have access to {organizations.length} workspaces. Switching changes which one
              every page reads from.
            </p>
            <ul className="ruled-list">
              {organizations.map((item) => (
                <li key={item.id} className="ruled-item">
                  <span>{item.name}</span>
                  <Button
                    variant="technical"
                    size="sm"
                    arrow={false}
                    disabled={item.id === organization?.id}
                    onClick={() => selectWorkspace(item)}
                  >
                    {item.id === organization?.id ? "Current" : "Switch"}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <section aria-labelledby="create-workspace-heading" className="stack stack-4">
        <h2 id="create-workspace-heading" className="heading-subsection">
          Create a workspace
        </h2>
        <p className="text-caption">
          A workspace is an organization: a club, an academy, a federation or a single analysis
          department. It is the data boundary — nothing is shared between workspaces.
        </p>

        <CreateWorkspaceForm
          onCreated={(created) => {
            refresh();
            selectWorkspace({
              id: created.id,
              name: created.name,
              slug: created.slug,
              role: "owner",
            });
          }}
        />
      </section>

      <section aria-labelledby="workspace-limits-heading" className="stack stack-4">
        <h2 id="workspace-limits-heading" className="heading-subsection">
          Not available yet
        </h2>

        <PlannedState
          title="Renaming and deleting workspaces"
          description="The organization endpoint supports creating and reading. Editing, archiving and deletion — including the data-return guarantees a customer needs before they rely on the platform — are not implemented, so no control is offered for them."
          note="Not available yet. Organization management needs sign-in and access control."
        />
      </section>
    </div>
  );
}

function CreateWorkspaceForm({ onCreated }: { onCreated: (organization: Organization) => void }) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);

  const { state, mutate } = useApiMutation(createOrganization);
  const submitting = state.status === "pending";
  const failure = state.status === "error" ? state.error : null;

  const effectiveSlug = slugTouched ? slug : slugify(name);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const created = await mutate({ name: name.trim(), slug: effectiveSlug });
    if (created) {
      setName("");
      setSlug("");
      setSlugTouched(false);
      onCreated(created);
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit} noValidate>
      {failure ? <FormError error={failure} /> : null}

      <Field
        id="org-name"
        label="Organization name"
        required
        hint="For example “Riverside FC”."
        value={name}
        onChange={(event) => setName(event.target.value)}
        error={apiErrorFor(failure, "name")}
      />

      <Field
        id="org-slug"
        label="Short name"
        required
        hint="Used in URLs. Lowercase letters, numbers and single hyphens."
        value={effectiveSlug}
        onChange={(event) => {
          setSlugTouched(true);
          setSlug(event.target.value);
        }}
        error={apiErrorFor(failure, "slug")}
      />

      <div className="form-actions">
        <Button
          type="submit"
          variant="primary"
          size="md"
          disabled={submitting || name.trim() === "" || effectiveSlug === ""}
        >
          {submitting ? "Creating…" : "Create workspace"}
        </Button>
      </div>
    </form>
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
