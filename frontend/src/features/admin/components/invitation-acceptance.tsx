"use client";

import { useEffect, useRef, useState } from "react";

import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FormError } from "@/components/ui/form";
import { LoadingState } from "@/components/ui/loading-state";
import { StateBlock } from "@/components/ui/states";
import { ApiError, NetworkError } from "@/lib/api-errors";
import { useSession } from "@/features/auth/session";
import { acceptInvitation } from "@/services/admin";

export interface InvitationAcceptanceProps {
  readonly token: string;
}

/* The token is handed to the API and then forgotten. It is never persisted, and
   it never appears in a URL the app navigates to or in any storage. */
export function InvitationAcceptance({ token }: InvitationAcceptanceProps) {
  const { user } = useSession();

  const [state, setState] = useState<"accepting" | "accepted" | "failed">(
    token ? "accepting" : "failed",
  );
  const [error, setError] = useState<Error | null>(
    token ? null : new ApiError(404, "not_found", "This invitation link is missing its token."),
  );
  const submitted = useRef(false);

  useEffect(() => {
    if (!token || !user) return;
    if (submitted.current) return;

    submitted.current = true;
    let ignore = false;

    acceptInvitation(token)
      .then(() => {
        if (!ignore) setState("accepted");
      })
      .catch((cause: unknown) => {
        if (ignore) return;
        setError(cause instanceof Error ? cause : new Error("The request failed."));
        setState("failed");
      });

    return () => {
      ignore = true;
    };
  }, [token, user]);

  if (!token) {
    return (
      <StateBlock
        tone="error"
        title="This invitation link is incomplete"
        description="The link is missing its token. Open the link from the invitation email without editing it."
        actions={
          <ButtonLink href="/dashboard" variant="technical" size="md">
            Back to the dashboard
          </ButtonLink>
        }
      />
    );
  }

  if (!user) {
    return (
      <Card>
        <div className="stack stack-4">
          <p className="text-body">
            Sign in with the address this invitation was sent to, then reopen the link.
          </p>
          <div className="form-actions">
            <ButtonLink
              href={`/sign-in?from=${encodeURIComponent(`/admin/invitation?token=${token}`)}`}
              variant="primary"
              size="md"
            >
              Sign in
            </ButtonLink>
          </div>
        </div>
      </Card>
    );
  }

  if (state === "failed") {
    return <InvitationFailure error={error ?? new Error("The request failed.")} />;
  }

  if (state === "accepted") {
    return (
      <StateBlock
        tone="empty"
        title="Invitation accepted"
        description={
          <>
            <p>
              You are now an invited platform administrator. This does not grant access yet —
              administrative access activates once a second factor is enrolled and confirmed.
            </p>
          </>
        }
        actions={
          <ButtonLink href="/admin/security" variant="primary" size="md">
            Continue to security setup
          </ButtonLink>
        }
      />
    );
  }

  return <LoadingState label="Accepting your invitation" rows={2} />;
}

/* Expired, revoked, already-used and unknown tokens are all refused by the
   backend: an expired or spent invitation answers 409, an unknown token 404, and
   a malformed one 422. Each gets copy that names the likely cause. */
function InvitationFailure({ error }: { error: Error }) {
  if (error instanceof NetworkError) {
    return <FormError error={error} />;
  }

  if (error instanceof ApiError) {
    if (error.status === 404) {
      return (
        <StateBlock
          tone="error"
          title="This invitation is not valid"
          description="The link may be mistyped or the invitation may have been replaced by a newer one. Ask an administrator to resend it."
          actions={
            <ButtonLink href="/dashboard" variant="technical" size="md">
              Back to the dashboard
            </ButtonLink>
          }
        />
      );
    }

    if (error.status === 409) {
      return (
        <StateBlock
          tone="error"
          title="This invitation is no longer usable"
          description="It may have expired, been revoked, or already been used. Ask an administrator to send a new invitation."
          actions={
            <ButtonLink href="/dashboard" variant="technical" size="md">
              Back to the dashboard
            </ButtonLink>
          }
        />
      );
    }

    if (error.status === 422) {
      return (
        <StateBlock
          tone="error"
          title="That invitation link is malformed"
          description="Open the link from the invitation email without editing it."
          actions={
            <ButtonLink href="/dashboard" variant="technical" size="md">
              Back to the dashboard
            </ButtonLink>
          }
        />
      );
    }

    if (error.status === 429) {
      return (
        <StateBlock
          tone="error"
          title="Too many attempts"
          description="Wait a little while before trying the invitation link again."
        />
      );
    }
  }

  return <FormError error={error} />;
}
