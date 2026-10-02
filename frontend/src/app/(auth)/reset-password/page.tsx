"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthPageShell } from "@/components/auth/auth-shell";
import { PasswordField, PasswordStrengthMeter } from "@/components/auth/password-field";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiErrorFor, FormError } from "@/components/ui/form";
import { LoadingState } from "@/components/ui/loading-state";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { resetPassword } from "@/services/auth";

export default function ResetPasswordPage() {
  return (
    <AuthPageShell
      title="Choose a new password"
      description="Setting a new password ends every session on the account, including any you did not start."
    >
      <Suspense fallback={<LoadingState label="Loading" rows={2} />}>
        <ResetForm />
      </Suspense>

      <p className="text-caption">
        <Link className="app-row-link" href="/sign-in">
          Back to sign in
        </Link>
      </p>
    </AuthPageShell>
  );
}

function ResetForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [newPassword, setNewPassword] = useState("");
  const [completed, setCompleted] = useState(false);

  const { state, mutate } = useApiMutation(resetPassword);
  const submitting = state.status === "pending";
  const failure = state.status === "error" ? state.error : null;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const accepted = await mutate({ token, new_password: newPassword });
    if (accepted) {
      setCompleted(true);
      setNewPassword("");
    }
  }

  if (!token) {
    return (
      <Banner tone="error" title="This link is incomplete">
        <p>
          The reset link is missing its token. Request a new one from the{" "}
          <Link className="app-row-link" href="/forgot-password">
            password reset page
          </Link>
          .
        </p>
      </Banner>
    );
  }

  if (completed) {
    return (
      <Card>
        <Banner tone="success" title="Password changed">
          <p>Every session has been signed out. Sign in again with your new password.</p>
        </Banner>
        <div className="form-actions" style={{ marginTop: "var(--space-5)" }}>
          <Button variant="primary" size="md" onClick={() => router.replace("/sign-in")}>
            Go to sign in
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <form className="form" onSubmit={handleSubmit} noValidate>
        {failure ? <FormError error={failure} /> : null}

        <PasswordField
          id="reset-password"
          label="New password"
          required
          autoComplete="new-password"
          hint="At least 10 characters, including a letter and a number."
          value={newPassword}
          onChange={setNewPassword}
          error={apiErrorFor(failure, "new_password")}
          strength={<PasswordStrengthMeter value={newPassword} />}
        />

        <div className="form-actions">
          <Button
            type="submit"
            variant="primary"
            size="md"
            disabled={submitting || newPassword === ""}
          >
            {submitting ? "Saving…" : "Set new password"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
