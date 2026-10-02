"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";

import { StateBlock } from "@/components/ui/states";
import { ButtonLink } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";
import { ErrorState } from "@/components/ui/error-state";
import { useAdminSession } from "@/features/admin/session";
import { useSession } from "@/features/auth/session";

export interface RequireAdminProps {
  readonly from: string;
  readonly children: ReactNode;
}

/* Route protection is a user-experience boundary, not a security one: every
   administrative request is separately authorized by the backend, and this
   component only decides which screen is worth showing. */
export function RequireAdmin({ from, children }: RequireAdminProps) {
  const { status: sessionStatus } = useSession();
  const { status, access } = useAdminSession();
  const router = useRouter();

  useEffect(() => {
    if (sessionStatus !== "unauthenticated") return;
    router.replace(`/sign-in?from=${encodeURIComponent(from)}`);
  }, [sessionStatus, from, router]);

  if (sessionStatus === "loading" || (sessionStatus === "authenticated" && status === "loading")) {
    return (
      <div className="centered-viewport container-page">
        <LoadingState label="Checking your administrative access" rows={2} />
      </div>
    );
  }

  if (access.state === "anonymous") {
    return (
      <div className="centered-viewport container-page">
        <LoadingState label="Redirecting to sign in" rows={1} />
      </div>
    );
  }

  if (access.state === "authenticated-non-admin") {
    return (
      <div className="container-page" style={{ paddingBlock: "var(--space-10)" }}>
        <StateBlock
          tone="empty"
          title="Platform administration"
          description="This account does not have administrative access. If you were expecting it, ask a platform administrator to invite you."
          actions={
            <ButtonLink href="/dashboard" variant="primary" size="md">
              Back to the dashboard
            </ButtonLink>
          }
        />
      </div>
    );
  }

  if (access.state === "admin-suspended" || access.state === "admin-revoked") {
    return (
      <div className="container-page" style={{ paddingBlock: "var(--space-10)" }}>
        <StateBlock
          tone="empty"
          title="Administrative access is unavailable"
          description={
            access.state === "admin-suspended"
              ? "This administrator account is suspended. An administrator with manage privileges can reactivate it."
              : "This administrator account has been revoked. Revocation is permanent."
          }
          actions={
            <ButtonLink href="/dashboard" variant="primary" size="md">
              Back to the dashboard
            </ButtonLink>
          }
        />
      </div>
    );
  }

  if (access.state === "admin-mfa-required" || access.state === "admin-invited") {
    return (
      <div className="container-page" style={{ paddingBlock: "var(--space-10)" }}>
        <StateBlock
          tone="placeholder"
          title="A second factor is required"
          description="Administrative access requires a verified authenticator. Continue to the security step to finish setting up access."
          actions={
            <ButtonLink href="/admin/security" variant="primary" size="md">
              Continue security setup
            </ButtonLink>
          }
        />
      </div>
    );
  }

  if (access.state === "error") {
    return (
      <div className="container-page" style={{ paddingBlock: "var(--space-10)" }}>
        <ErrorState error={access.error} />
      </div>
    );
  }

  return <>{children}</>;
}
