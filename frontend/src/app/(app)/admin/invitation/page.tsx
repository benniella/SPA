"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { LoadingState } from "@/components/ui/loading-state";
import { InvitationAcceptance } from "@/features/admin";

/* The token arrives in the query string of the emailed link and is read once.
   Nothing is written to browser storage, and the token is not echoed back into
   the DOM beyond this flow. */
export default function InvitationPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading invitation" rows={2} />}>
      <InvitationToken />
    </Suspense>
  );
}

function InvitationToken() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  return (
    <section
      aria-labelledby="invitation-heading"
      className="container-page"
      style={{ paddingBlock: "var(--space-10)" }}
    >
      <div className="stack stack-6">
        <header className="stack stack-3">
          <h1 id="invitation-heading" className="heading-page">
            Platform administration invitation
          </h1>
          <p className="text-body">
            Review and accept your invitation to administer SPA. Accepting does not grant access
            until you have enrolled a second factor.
          </p>
        </header>

        <InvitationAcceptance token={token} />
      </div>
    </section>
  );
}
