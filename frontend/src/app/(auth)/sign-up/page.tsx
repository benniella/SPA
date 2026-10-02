"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthPageShell } from "@/components/auth/auth-shell";
import { PasswordField, PasswordStrengthMeter } from "@/components/auth/password-field";
import { Button } from "@/components/ui/button";
import { Field, FormError, apiErrorFor } from "@/components/ui/form";
import { EmailField } from "@/components/ui/email-field";
import { slugify } from "@/features/teams";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { isValidEmail, phoneValidationMessage } from "@/lib/validators";
import { register } from "@/services/auth";

export default function SignUpPage() {
  return (
    <AuthPageShell
      title="Create an account"
      description="Register your identity and name the workspace your data belongs to."
      menu="signUp"
    >
      <SignUpForm />

      <p className="text-caption">
        Already have an account?{" "}
        <Link className="app-row-link" href="/sign-in">
          Sign in
        </Link>
      </p>
    </AuthPageShell>
  );
}

function SignUpForm() {
  const router = useRouter();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [emailError, setEmailError] = useState<string | undefined>();
  const [passwordError, setPasswordError] = useState<string | undefined>();

  const { state, mutate } = useApiMutation(register);
  const submitting = state.status === "pending";
  const failure = state.status === "error" ? state.error : null;

  const effectiveSlug = slugTouched ? slug : slugify(organizationName);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedEmail = email.trim();
    if (trimmedEmail && !isValidEmail(trimmedEmail)) {
      setEmailError("Enter a valid email address.");
      return;
    }

    setEmailError(undefined);

    if (confirmPassword !== password) {
      setPasswordError("Both passwords must match.");
      return;
    }

    setPasswordError(undefined);

    const accepted = await mutate({
      email: trimmedEmail,
      password,
      display_name: displayName.trim(),
      organization_name: organizationName.trim(),
      organization_slug: effectiveSlug,
    });
    if (!accepted) return;

    // Registration deliberately does not sign the account in: the address has to
    // be confirmed first, and the verification link is what does that.
    router.replace("/verify-email");
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
        error={apiErrorFor(failure, "display_name")}
      />

      <EmailField
        id="signup-email"
        label="Email address"
        required
        autoComplete="email"
        value={email}
        onChange={setEmail}
        error={emailError ?? apiErrorFor(failure, "email")}
      />

      <PasswordField
        id="signup-password"
        label="Password"
        required
        autoComplete="new-password"
        hint="At least 10 characters, including a letter and a number."
        value={password}
        onChange={setPassword}
        error={apiErrorFor(failure, "password")}
        strength={<PasswordStrengthMeter value={password} />}
      />

      <PasswordField
        id="signup-confirm-password"
        label="Confirm password"
        required
        autoComplete="new-password"
        value={confirmPassword}
        onChange={setConfirmPassword}
        error={passwordError}
      />

      <Field
        id="signup-phone"
        label="Phone number"
        type="tel"
        inputMode="tel"
        autoComplete="tel"
        hint="Optional. Used for match-day notifications."
        value={phoneNumber}
        onChange={(event) => setPhoneNumber(event.target.value)}
        error={phoneValidationMessage(phoneNumber) ?? apiErrorFor(failure, "phone_number")}
      />

      <Field
        id="signup-org-name"
        label="Organization name"
        required
        hint="For example “Riverside FC”."
        value={organizationName}
        onChange={(event) => setOrganizationName(event.target.value)}
        error={apiErrorFor(failure, "organization_name")}
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
        error={apiErrorFor(failure, "organization_slug")}
      />

      <div className="form-actions">
        <Button
          type="submit"
          variant="primary"
          size="md"
          arrow={false}
          disabled={
            submitting ||
            displayName.trim() === "" ||
            email.trim() === "" ||
            password === "" ||
            confirmPassword === "" ||
            organizationName.trim() === "" ||
            effectiveSlug === ""
          }
        >
          {submitting ? "Creating…" : "Create account"}
        </Button>
      </div>
    </form>
  );
}
