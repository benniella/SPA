"use client";

import Link from "next/link";
import { useState } from "react";

import { AuthPageShell } from "@/components/auth/auth-shell";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmailField } from "@/components/ui/email-field";
import { FormError, apiErrorFor } from "@/components/ui/form";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { isValidEmail } from "@/lib/validators";
import { forgotPassword } from "@/services/auth";

export default function ForgotPasswordPage() {
  return (
    <AuthPageShell
      title="Reset your password"
      description="Enter your email address and we will send a link to choose a new password."
    >
      <ResetRequestForm />

      <p className="text-caption">
        <Link className="app-row-link" href="/sign-in">
          Back to sign in
        </Link>
      </p>
    </AuthPageShell>
  );
}

function ResetRequestForm() {
  const [email, setEmail] = useState("");
  const [requested, setRequested] = useState(false);
  const [emailError, setEmailError] = useState<string | undefined>();

  const { state, mutate } = useApiMutation(forgotPassword);
  const submitting = state.status === "pending";
  const failure = state.status === "error" ? state.error : null;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedEmail = email.trim();
    if (trimmedEmail && !isValidEmail(trimmedEmail)) {
      setEmailError("Enter a valid email address.");
      return;
    }

    setEmailError(undefined);
    const accepted = await mutate(trimmedEmail);
    if (accepted) {
      setRequested(true);
      setEmail("");
    }
  }

  return (
    <Card>
      {/* The message is the same whether or not the address has an account, because
          saying otherwise would turn this page into a way to discover who is
          registered. */}
      {requested ? (
        <Banner tone="success" title="Check your email">
          <p>
            If an account exists for that address, a password reset link is on its way. The link
            expires shortly, so use it soon.
          </p>
        </Banner>
      ) : null}

      <form className="form" onSubmit={handleSubmit} noValidate>
        {failure ? <FormError error={failure} /> : null}

        <EmailField
          id="forgot-email"
          label="Email address"
          required
          autoComplete="email"
          value={email}
          onChange={setEmail}
          error={emailError ?? apiErrorFor(failure, "email")}
        />

        <div className="form-actions">
          <Button
            type="submit"
            variant="primary"
            size="md"
            disabled={submitting || email.trim() === ""}
          >
            {submitting ? "Sending…" : "Send reset link"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
