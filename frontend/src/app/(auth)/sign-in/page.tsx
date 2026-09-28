"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { BrandMark } from "@/components/brand/brand-mark";
import { Banner } from "@/components/ui/banner";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiErrorFor, Field, FormError } from "@/components/ui/form";
import { LoadingState } from "@/components/ui/loading-state";
import { Container } from "@/components/ui/section";
import { isProtectedPath } from "@/data/app-navigation";
import { SessionProvider, useSession } from "@/features/auth/session";
import { slugify } from "@/features/teams";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { createOrganization } from "@/services/organizations";
import type { Organization } from "@/types/api";

export default function SignInPage() {
  return (
    <SessionProvider>
      <Container width="narrow">
        <div className="stack stack-6" style={{ paddingBlock: "var(--space-9)" }}>
          <div className="stack stack-4">
            <BrandMark variant="full" />
            <h1 className="heading-page">Sign in</h1>
            <p className="text-body">Choose the workspace to work in.</p>
          </div>

          <Banner tone="warning" title="Sign-in is not available yet">
            <p>
              Accounts, sign-in and permissions are still being built. Until they arrive, choosing a
              workspace opens the application in this browser only.
            </p>
          </Banner>

          {/* 'useSearchParams' needs a Suspense boundary, or the whole page opts out
              of static rendering. */}
          <Suspense fallback={<LoadingState label="Loading workspaces" rows={3} />}>
            <WorkspaceEntry />
          </Suspense>

          <p className="text-caption">
            <Link className="app-row-link" href="/">
              Back to the SPA overview
            </Link>
          </p>
        </div>
      </Container>
    </SessionProvider>
  );
}

function WorkspaceEntry() {
  const { organizations, organizationsStatus, selectWorkspace, refreshOrganizations } =
    useSession();
  const router = useRouter();
  const searchParams = useSearchParams();

  const from = safeReturnPath(searchParams.get("from"));

  function enter(organization: Organization) {
    selectWorkspace(organization);
    router.replace(from);
  }

  if (organizationsStatus === "loading") {
    return <LoadingState label="Loading workspaces" rows={3} />;
  }

  if (organizationsStatus === "error") {
    return (
      <Banner tone="error" title="The SPA API could not be reached">
        <p>
          Workspaces are read from the API, so none can be listed while it is unreachable. Until we
          deploy the app on a server, but currently on testing locally. its is mot working as
          expected. Please ensure the API is running — in a development machine that is{" "}
          <code>make backend-dev</code>.
        </p>
      </Banner>
    );
  }

  if (organizations.length === 0) {
    return (
      <div className="stack stack-5">
        <div className="stack stack-2">
          <h2 className="heading-subsection">Create your first workspace</h2>
          <p className="text-body">
            No organization exists yet. A workspace is the boundary everything else belongs to, so
            it is the first thing to create.
          </p>
        </div>

        <WorkspaceForm
          submitLabel="Create and continue"
          onCreated={(created) => {
            refreshOrganizations();
            enter(created);
          }}
        />
      </div>
    );
  }

  return (
    <div className="stack stack-5">
      <h2 className="heading-subsection">Choose a workspace</h2>

      <ul className="ruled-list">
        {organizations.map((organization) => (
          <li key={organization.id} className="ruled-item">
            <span className="stack stack-1">
              <span className="data-table-primary">{organization.name}</span>
              <span className="app-row-meta">{organization.slug}</span>
            </span>
            <Button variant="technical" size="sm" onClick={() => enter(organization)}>
              Open
            </Button>
          </li>
        ))}
      </ul>

      <Card>
        <h3 className="heading-card">Create another workspace</h3>
        <p className="text-caption" style={{ marginTop: "var(--space-2)" }}>
          A separate club, academy or analysis department gets its own workspace and its own data.
        </p>
        <div style={{ marginTop: "var(--space-4)" }}>
          <WorkspaceForm submitLabel="Create" onCreated={enter} />
        </div>
      </Card>
    </div>
  );
}

function WorkspaceForm({
  submitLabel,
  onCreated,
}: {
  submitLabel: string;
  onCreated: (organization: Organization) => void;
}) {
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
        id="signin-org-name"
        label="Organization name"
        required
        hint="For example “Riverside FC”."
        value={name}
        onChange={(event) => setName(event.target.value)}
        error={apiErrorFor(failure, "name")}
      />

      <Field
        id="signin-org-slug"
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
          {submitting ? "Creating…" : submitLabel}
        </Button>

        <ButtonLink href="/" variant="technical" size="md">
          Cancel
        </ButtonLink>
      </div>
    </form>
  );
}

function safeReturnPath(value: string | null): string {
  if (!value) return "/dashboard";
  if (!value.startsWith("/")) return "/dashboard";
  if (value.startsWith("//")) return "/dashboard";
  if (!isProtectedPath(value)) return "/dashboard";
  return value;
}
