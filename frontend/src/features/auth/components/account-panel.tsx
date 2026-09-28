"use client";

import { Button, ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PlannedState } from "@/components/ui/states";
import { useSession } from "@/features/auth/session";

export function AccountPanel() {
  const { organization, signOut } = useSession();

  return (
    <div className="stack stack-7">
      <section aria-labelledby="session-heading" className="stack stack-4">
        <h2 id="session-heading" className="heading-subsection">
          Session
        </h2>

        <Card>
          <dl className="fact-list">
            <Fact label="Identity" value="Not established" />
            <Fact label="Signed in as" value="No account is attached to this session" />
            <Fact label="Workspace" value={organization?.name ?? "None selected"} />
            <Fact label="Authentication" value="Not implemented" />
          </dl>

          <div
            className="form-actions"
            style={{ borderTop: "1px solid var(--color-border)", marginTop: "var(--space-5)" }}
          >
            <Button variant="technical" size="md" arrow={false} onClick={signOut}>
              Sign out
            </Button>
            <ButtonLink href="/settings" variant="technical" size="md">
              Workspace settings
            </ButtonLink>
          </div>
        </Card>
      </section>

      <section aria-labelledby="auth-status-heading" className="stack stack-4">
        <h2 id="auth-status-heading" className="heading-subsection">
          Authentication
        </h2>

        <PlannedState
          title="Sign-in is not available yet"
          description={
            <>
              <p>
                Choosing a workspace sets the scope for this session, and that is all it does.
                Accounts, sign-in and permissions are still being built.
              </p>
              <p className="text-caption" style={{ marginTop: "var(--space-3)" }}>
                A development build marks the session as such in the header.
              </p>
            </>
          }
        />

        <div className="state-block" data-tone="placeholder">
          <h3 className="state-title">What sign-in has to decide</h3>
          <ul className="document-list" style={{ marginTop: "var(--space-3)" }}>
            <li className="document-list-item">
              The credential mechanism — session cookies, tokens, or an external identity provider.
              Club SSO is the deciding question, because if federated sign-in is required in the
              first year, building a credential system would be wasted work.
            </li>
            <li className="document-list-item">
              Session lifetime and refresh, and what happens to a request that arrives after expiry.
            </li>
            <li className="document-list-item">
              The invitation flow: how a user joins an organization, and who may invite.
            </li>
            <li className="document-list-item">
              Authorization granularity. <code>MembershipRole</code> has five roles and two coarse
              predicates; whether a coach and an analyst need different surfaces is still open.
            </li>
            <li className="document-list-item">
              How the API enforces tenancy once a caller is authenticated, rather than trusting the
              <code>organization_id</code> a client sends.
            </li>
          </ul>
        </div>
      </section>

      <section aria-labelledby="account-data-heading" className="stack stack-4">
        <h2 id="account-data-heading" className="heading-subsection">
          Account data
        </h2>

        <PlannedState
          title="No account management"
          description="Changing a display name, email address or password, and exporting or deleting an account, all depend on an account existing first. None of these flows is implemented."
          note="Not available yet. This needs sign-in."
        />
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
