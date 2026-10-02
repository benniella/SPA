"use client";

import { Button, ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useSession } from "@/features/auth/session";

export function AccountPanel() {
  const { user, organization, signOut } = useSession();

  return (
    <div className="stack stack-7">
      <section aria-labelledby="session-heading" className="stack stack-4">
        <h2 id="session-heading" className="heading-subsection">
          Session
        </h2>

        <Card>
          <dl className="fact-list">
            <Fact label="Identity" value={user?.email ?? "Not established"} />
            <Fact label="Signed in as" value={user?.display_name ?? "Unknown"} />
            <Fact label="Workspace" value={organization?.name ?? "None selected"} />
            <Fact label="Email verified" value={user?.email_verified ? "Yes" : "No"} />
          </dl>

          <div
            className="form-actions"
            style={{ borderTop: "1px solid var(--color-border)", marginTop: "var(--space-5)" }}
          >
            <Button variant="technical" size="md" arrow={false} onClick={() => void signOut()}>
              Sign out
            </Button>
            <ButtonLink href="/settings" variant="technical" size="md">
              Account settings
            </ButtonLink>
          </div>
        </Card>
      </section>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="fact">
      <dt className="fact-label">{label}</dt>
      <dd className="fact-value">{value}</dd>
    </div>
  );
}
