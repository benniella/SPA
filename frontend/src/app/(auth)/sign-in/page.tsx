"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AuthPageShell } from "@/components/auth/auth-shell";
import { PasswordInput } from "@/components/auth/password-input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CheckboxField } from "@/components/ui/checkbox-field";
import { EmailField } from "@/components/ui/email-field";
import { FormError, apiErrorFor } from "@/components/ui/form";
import { LoadingState } from "@/components/ui/loading-state";
import { isProtectedPath } from "@/data/app-navigation";
import { SessionProvider, useSession } from "@/features/auth/session";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { isValidEmail } from "@/lib/validators";
import { login } from "@/services/auth";

export default function SignInPage() {
  return (
    <SessionProvider>
      <AuthPageShell
        title="Sign in"
        description="Use the email address and password for your SPA account."
      >
        <Suspense fallback={<LoadingState label="Loading" rows={3} />}>
          <SignInForm />
        </Suspense>

        <p className="text-caption">
          No account yet?{" "}
          <Link className="app-row-link" href="/sign-up">
            Create one
          </Link>
        </p>
      </AuthPageShell>
    </SessionProvider>
  );
}

function SignInForm() {
  const { refresh } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const from = safeReturnPath(searchParams.get("from"));

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [emailError, setEmailError] = useState<string | undefined>();

  const { state, mutate } = useApiMutation(login);
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
    const signedIn = await mutate({ email: trimmedEmail, password });
    if (signedIn) {
      refresh();
      setRememberMe(false);
      setPassword("");
      router.replace(from);
    }
  }

  return (
    <Card>
      <form className="form" onSubmit={handleSubmit} noValidate>
        {failure ? <FormError error={failure} /> : null}

        <EmailField
          id="signin-email"
          label="Email address"
          required
          autoComplete="username"
          value={email}
          onChange={setEmail}
          error={emailError ?? apiErrorFor(failure, "email")}
        />

        <PasswordInput
          id="signin-password"
          label="Password"
          required
          autoComplete="current-password"
          value={password}
          onChange={setPassword}
          error={apiErrorFor(failure, "password")}
        />

        <div className="auth-signin-options">
          <CheckboxField
            id="signin-remember"
            label="Remember me"
            checked={rememberMe}
            onChange={setRememberMe}
          />
        </div>

        <div className="auth-signin-links">
          <Link className="app-row-link" href="/forgot-password">
            Forgot your password?
          </Link>
        </div>

        <div className="form-actions form-actions--center">
          <Button
            type="submit"
            variant="primary"
            size="md"
            arrow={false}
            disabled={submitting || email.trim() === "" || password === ""}
          >
            {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function safeReturnPath(value: string | null): string {
  if (!value) return "/dashboard";
  if (!value.startsWith("/")) return "/dashboard";
  if (value.startsWith("//")) return "/dashboard";
  if (!isProtectedPath(value)) return "/dashboard";
  return value;
}
