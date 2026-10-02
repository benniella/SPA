"use client";

import { Card } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { MfaChallenge } from "@/features/admin/components/mfa-challenge";
import { MfaEnrollment } from "@/features/admin/components/mfa-enrollment";
import { RecoveryCodes } from "@/features/admin/components/recovery-codes";
import { useAdminSession } from "@/features/admin/session";

/* The security screen is the single place an administrator resolves their second
   factor. Which step applies is decided by the backend-resolved access state, not
   by anything remembered in the browser. */
export function AdminSecurityPanel() {
  const { status, access, refresh } = useAdminSession();

  if (status === "loading") {
    return <LoadingState label="Checking your administrative access" rows={3} />;
  }

  if (access.state === "error") {
    return <ErrorState error={access.error} onRetry={refresh} />;
  }

  if (access.state === "authenticated-non-admin") {
    return (
      <Card>
        <p className="text-body">
          This account is not an administrator. An invitation from an existing administrator is
          required before a second factor can be enrolled.
        </p>
      </Card>
    );
  }

  if (access.state === "admin-suspended" || access.state === "admin-revoked") {
    return (
      <Card>
        <p className="text-body">
          This administrator account cannot enroll a second factor while it is{" "}
          {access.state === "admin-suspended" ? "suspended" : "revoked"}.
        </p>
      </Card>
    );
  }

  if (access.state === "admin-invited") {
    return (
      <section aria-labelledby="admin-enroll-heading" className="stack stack-4">
        <h2 id="admin-enroll-heading" className="heading-subsection">
          Enroll a second factor
        </h2>
        <p className="text-body">Administrative access activates once this step is complete.</p>
        <MfaEnrollment onEnrolled={refresh} />
      </section>
    );
  }

  if (access.state === "admin-mfa-required") {
    return (
      <section aria-labelledby="admin-challenge-heading" className="stack stack-4">
        <h2 id="admin-challenge-heading" className="heading-subsection">
          Verify your second factor
        </h2>
        <p className="text-body">
          This session has not yet satisfied the second factor required for administration.
        </p>
        <MfaChallenge onVerified={refresh} />
      </section>
    );
  }

  return (
    <section aria-labelledby="admin-recovery-heading" className="stack stack-4">
      <h2 id="admin-recovery-heading" className="heading-subsection">
        Recovery codes
      </h2>
      <p className="text-body">A fallback for when your authenticator is unavailable.</p>
      <RecoveryCodes />
    </section>
  );
}
