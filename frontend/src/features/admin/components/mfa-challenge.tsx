"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, FormError, apiErrorFor } from "@/components/ui/form";
import { ApiError } from "@/lib/api-errors";
import {
  satisfyChallengeWithRecoveryCode,
  satisfyChallengeWithTotp,
  startMfaChallenge,
} from "@/services/admin";
import { useApiMutation } from "@/hooks/use-api-mutation";

type ChallengeMethod = "totp" | "recovery-code";

export interface MfaChallengeProps {
  readonly onVerified: () => void;
}

export function MfaChallenge({ onVerified }: MfaChallengeProps) {
  const [method, setMethod] = useState<ChallengeMethod>("totp");
  const [code, setCode] = useState("");
  const [started, setStarted] = useState(false);
  const [challengeReady, setChallengeReady] = useState(false);

  const start = useApiMutation<void, unknown>(() => startMfaChallenge());
  const verify = useApiMutation<{ code: string }, unknown>((input) =>
    method === "totp" ? satisfyChallengeWithTotp(input) : satisfyChallengeWithRecoveryCode(input),
  );

  const starting = start.state.status === "pending";
  const verifying = verify.state.status === "pending";
  const startFailure = start.state.status === "error" ? start.state.error : null;
  const verifyFailure = verify.state.status === "error" ? verify.state.error : null;

  async function handleStart() {
    setStarted(true);
    const challenge = await start.mutate();
    if (!challenge) return;
    setChallengeReady(true);
  }

  async function handleVerify(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = await verify.mutate({ code: code.trim() });
    if (result !== undefined) {
      setCode("");
      onVerified();
    }
  }

  if (!challengeReady) {
    return (
      <Card>
        <div className="stack stack-4">
          <p className="text-body">
            Verify your identity with the second factor before continuing into administration.
          </p>

          {startFailure ? <FormError error={startFailure} /> : null}

          <div className="form-actions">
            <Button
              variant="primary"
              size="md"
              arrow={false}
              loading={starting}
              loadingLabel="Starting"
              onClick={() => void handleStart()}
            >
              {started && startFailure ? "Try again" : "Start verification"}
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="stack stack-6">
        <fieldset className="stack stack-3">
          <legend className="form-label">Verification method</legend>

          <div className="row-center" role="radiogroup" aria-label="Verification method">
            <MethodOption
              id="mfa-method-totp"
              label="Use authenticator"
              selected={method === "totp"}
              onSelect={() => {
                setMethod("totp");
                setCode("");
                verify.reset();
              }}
            />
            <MethodOption
              id="mfa-method-recovery"
              label="Use a recovery code"
              selected={method === "recovery-code"}
              onSelect={() => {
                setMethod("recovery-code");
                setCode("");
                verify.reset();
              }}
            />
          </div>
        </fieldset>

        <form className="form" onSubmit={handleVerify} noValidate>
          {verifyFailure ? <ChallengeError error={verifyFailure} /> : null}

          <Field
            id="mfa-challenge-code"
            label={method === "totp" ? "Authenticator code" : "Recovery code"}
            required
            inputMode={method === "totp" ? "numeric" : "text"}
            autoComplete="one-time-code"
            autoFocus
            value={code}
            onChange={(event) => setCode(event.target.value)}
            hint={
              method === "totp"
                ? "The current six-digit code from your authenticator."
                : "One of the recovery codes issued when you enrolled."
            }
            error={apiErrorFor(verifyFailure, "code")}
          />

          <div className="form-actions">
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={verifying || code.trim().length < 6}
            >
              {verifying ? "Verifying…" : "Verify"}
            </Button>
          </div>
        </form>
      </div>
    </Card>
  );
}

/* The backend distinguishes an invalid code (409), an absent or spent challenge
   (409), an unauthenticated session (401) and a rate limit (429). The UI names
   the rate limit explicitly because it is the only one with an actionable wait;
   the rest carry the backend's own message through the shared error copy. */
function ChallengeError({ error }: { error: Error }) {
  if (error instanceof ApiError && error.status === 429) {
    const retryAfter = error.details?.["retry_after_seconds"];
    return (
      <div className="state-block" data-tone="error" role="alert">
        <h2 className="state-title">Too many attempts</h2>
        <p className="state-text">
          {typeof retryAfter === "number"
            ? `Try again in about ${Math.ceil(retryAfter / 60)} minute(s).`
            : "Too many attempts. Try again shortly."}
        </p>
      </div>
    );
  }

  return <FormError error={error} />;
}

function MethodOption({
  id,
  label,
  selected,
  onSelect,
}: {
  id: string;
  label: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <label htmlFor={id} className="row-center" style={{ gap: "var(--space-2)" }}>
      <input
        id={id}
        type="radio"
        name="mfa-method"
        checked={selected}
        onChange={onSelect}
        value={id}
      />
      <span>{label}</span>
    </label>
  );
}
