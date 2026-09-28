"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { BrandMark } from "@/components/brand/brand-mark";
import { Banner } from "@/components/ui/banner";
import { Button, ButtonLink } from "@/components/ui/button";
import { apiErrorFor, Field, FormError } from "@/components/ui/form";
import { Container } from "@/components/ui/section";
import { slugify } from "@/features/teams";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { createOrganization } from "@/services/organizations";
import { createUser } from "@/services/users";

export default function SignUpPage() {
  return (
    <Container width="narrow">
      <div className="stack stack-6" style={{ paddingBlock: "var(--space-9)" }}>
        <div className="stack stack-4">
          <BrandMark variant="full" />
          <h1 className="heading-page">Create an account</h1>
          <p className="text-body">
            Register your identity, then name the workspace your data belongs to.
          </p>
        </div>

        <Banner tone="warning" title="Sign-up is not available yet">
          <p>
            Accounts, credentials and permissions are still being built. Until they arrive, this
            creates the identity record only — no password is stored and nothing is signed in.
          </p>
        </Banner>

        <SignUpForm />

        <p className="text-caption">
          Already have a workspace?{" "}
          <Link className="app-row-link" href="/sign-in">
            Sign in
          </Link>
        </p>
      </div>
    </Container>
  );
}

function SignUpForm() {
  const router = useRouter();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);

  const user = useApiMutation(createUser);
  const organization = useApiMutation(createOrganization);
  const submitting = user.state.status === "pending" || organization.state.status === "pending";
  const failure =
    user.state.status === "error"
      ? user.state.error
      : organization.state.status === "error"
        ? organization.state.error
        : null;

  const effectiveSlug = slugTouched ? slug : slugify(organizationName);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const created = await user.mutate({ email: email.trim(), display_name: displayName.trim() });
    if (!created) return;

    const createdWorkspace = await organization.mutate({
      name: organizationName.trim(),
      slug: effectiveSlug,
    });
    if (!createdWorkspace) return;

    // The workspace exists, but no session does: signing in is where one is chosen.
    router.replace("/sign-in");
  }

  return (
    <form className="form" onSubmit={handleSubmit} noValidate>
      {failure ? <FormError error={failure} /> : null}

      <Field
        id="signup-name"
        label="Your name"
        required
        autoComplete="name"
        hint="How you will be identified in the workspace."
        value={displayName}
        onChange={(event) => setDisplayName(event.target.value)}
        error={apiErrorFor(user.state.status === "error" ? user.state.error : null, "display_name")}
      />

      <Field
        id="signup-email"
        label="Email address"
        type="email"
        required
        autoComplete="email"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        error={apiErrorFor(user.state.status === "error" ? user.state.error : null, "email")}
      />

      <Field
        id="signup-org-name"
        label="Organization name"
        required
        hint="For example “Riverside FC”."
        value={organizationName}
        onChange={(event) => setOrganizationName(event.target.value)}
        error={apiErrorFor(
          organization.state.status === "error" ? organization.state.error : null,
          "name",
        )}
      />

      <Field
        id="signup-org-slug"
        label="Short name"
        required
        hint="Used in URLs. Lowercase letters, numbers and single hyphens."
        value={effectiveSlug}
        onChange={(event) => {
          setSlugTouched(true);
          setSlug(event.target.value);
        }}
        error={apiErrorFor(
          organization.state.status === "error" ? organization.state.error : null,
          "slug",
        )}
      />

      <div className="form-actions">
        <Button
          type="submit"
          variant="primary"
          size="md"
          disabled={
            submitting ||
            displayName.trim() === "" ||
            email.trim() === "" ||
            organizationName.trim() === "" ||
            effectiveSlug === ""
          }
        >
          {submitting ? "Creating…" : "Create account"}
        </Button>

        <ButtonLink href="/" variant="technical" size="md">
          Cancel
        </ButtonLink>
      </div>
    </form>
  );
}
