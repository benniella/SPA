"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, FormError, apiErrorFor } from "@/components/ui/form";
import { beginMfaEnrollment, confirmMfaEnrollment } from "@/services/admin";
import { useApiMutation } from "@/hooks/use-api-mutation";
import type { MfaEnrollmentMaterial } from "@/types/api";

export interface MfaEnrollmentProps {
  readonly onEnrolled: () => void;
}

/* The secret and provisioning URI arrive once, for the user to configure an
   authenticator. They live in component state only and are never written to
   browser storage or logged. */
export function MfaEnrollment({ onEnrolled }: MfaEnrollmentProps) {
  const [material, setMaterial] = useState<MfaEnrollmentMaterial | null>(null);
  const [code, setCode] = useState("");
  const [started, setStarted] = useState(false);

  const begin = useApiMutation<void, MfaEnrollmentMaterial>(() => beginMfaEnrollment());
  const confirm = useApiMutation<{ code: string }, unknown>((input) => confirmMfaEnrollment(input));

  const beginning = begin.state.status === "pending";
  const confirming = confirm.state.status === "pending";
  const beginFailure = begin.state.status === "error" ? begin.state.error : null;
  const confirmFailure = confirm.state.status === "error" ? confirm.state.error : null;

  async function handleBegin() {
    setStarted(true);
    const issued = await begin.mutate();
    if (!issued) return;
    setMaterial(issued);
  }

  async function handleConfirm(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = await confirm.mutate({ code: code.trim() });
    if (result) {
      setMaterial(null);
      setCode("");
      onEnrolled();
    }
  }

  if (!material) {
    return (
      <Card>
        <div className="stack stack-4">
          <p className="text-body">
            Administrator access requires a second factor. SPA uses a time-based one-time password,
            which works with any standard authenticator application.
          </p>

          {beginFailure ? <FormError error={beginFailure} /> : null}

          <div className="form-actions">
            <Button
              variant="primary"
              size="md"
              arrow={false}
              loading={beginning}
              loadingLabel="Preparing"
              onClick={() => void handleBegin()}
            >
              {started && beginFailure ? "Try again" : "Begin enrollment"}
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="stack stack-6">
        <section aria-labelledby="mfa-configure-heading" className="stack stack-4">
          <h2 id="mfa-configure-heading" className="heading-subsection">
            Configure your authenticator
          </h2>

          <p className="text-body">
            Add the account below to your authenticator application, then enter the six-digit code
            it produces.
          </p>

          <dl className="fact-list">
            <div className="fact">
              <dt className="fact-label">Setup key</dt>
              <dd className="fact-value">
                <code className="data-table-primary">{material.secret}</code>
              </dd>
            </div>
            <div className="fact">
              <dt className="fact-label">Provisioning URI</dt>
              <dd className="fact-value">
                <span className="text-caption" style={{ wordBreak: "break-all" }}>
                  {material.provisioning_uri}
                </span>
              </dd>
            </div>
          </dl>

          <p className="text-caption">
            This key is shown once. It is not stored in this browser and cannot be retrieved later.
          </p>
        </section>

        <form className="form" onSubmit={handleConfirm} noValidate>
          {confirmFailure ? <FormError error={confirmFailure} /> : null}

          <Field
            id="mfa-enroll-code"
            label="Authenticator code"
            required
            inputMode="numeric"
            autoComplete="one-time-code"
            autoFocus
            value={code}
            onChange={(event) => setCode(event.target.value)}
            hint="The current six-digit code."
            error={apiErrorFor(confirmFailure, "code")}
          />

          <div className="form-actions">
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={confirming || code.trim().length < 6}
            >
              {confirming ? "Confirming…" : "Confirm enrollment"}
            </Button>
          </div>
        </form>
      </div>
    </Card>
  );
}
