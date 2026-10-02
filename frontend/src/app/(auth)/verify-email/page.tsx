"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AuthPageShell } from "@/components/auth/auth-shell";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmailField } from "@/components/ui/email-field";
import { FormError, apiErrorFor } from "@/components/ui/form";
import { LoadingState } from "@/components/ui/loading-state";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { isValidEmail } from "@/lib/validators";
import { resendVerification, verifyEmail } from "@/services/auth";

export default function VerifyEmailPage() {
  return (
    <AuthPageShell
      title="Verify your email"
      description="We sent a verification link to your address. Opening it confirms the account."
    >
      <Suspense fallback={<LoadingState label="Checking your link" rows={2} />}>
        <VerificationStatus />
      </Suspense>

      <ResendForm />

      <p className="text-caption">
        <Link className="app-row-link" href="/sign-in">
          Back to sign in
        </Link>
      </p>
    </AuthPageShell>
  );
}

function VerificationStatus() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [state, setState] = useState<"idle" | "verifying" | "verified" | "failed">("idle");

  useEffect(() => {
    if (!token) return;
    let ignore = false;

    async function confirm() {
      setState("verifying");
      try {
        await verifyEmail(token as string);
        if (ignore) return;
        setState("verified");
        router.replace("/dashboard");
      } catch {
        if (ignore) return;
        setState("failed");
      }
    }

    void confirm();

    return () => {
      ignore = true;
    };
  }, [token, router]);

  if (!token) return null;

  if (state === "verified") {
    return (
      <Banner tone="success" title="Email verified">
        <p>Your account is confirmed. Taking you to the application…</p>
      </Banner>
    );
  }

  if (state === "failed") {
    return (
      <Banner tone="error" title="That link is not valid">
        <p>The verification link has expired or has already been used. Request a new one below.</p>
      </Banner>
    );
  }

  return <LoadingState label="Verifying your email" rows={2} />;
}

function ResendForm() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [emailError, setEmailError] = useState<string | undefined>();

  const { state, mutate } = useApiMutation(resendVerification);
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
      setSent(true);
      setEmail("");
    }
  }

  return (
    <Card>
      <h2 className="heading-card">Send a new link</h2>
      <p className="text-caption" style={{ marginTop: "var(--space-2)" }}>
        Enter your address and we will send a fresh verification link.
      </p>

      {sent ? (
        <Banner tone="success" title="Link requested">
          <p>If that address has an account waiting to be verified, a new link is on its way.</p>
        </Banner>
      ) : null}

      <form
        className="form"
        onSubmit={handleSubmit}
        noValidate
        style={{ marginTop: "var(--space-4)" }}
      >
        {failure ? <FormError error={failure} /> : null}

        <EmailField
          id="verify-email-address"
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
            {submitting ? "Sending…" : "Send link"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
