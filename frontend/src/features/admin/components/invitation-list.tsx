"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";
import { ErrorState } from "@/components/ui/error-state";
import { FormError, SelectField } from "@/components/ui/form";
import { LoadingState } from "@/components/ui/loading-state";
import { formatDateTime } from "@/lib/format";
import { listInvitations, resendInvitation, revokeInvitation } from "@/services/admin";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { useApiQuery } from "@/hooks/use-api-query";
import type { Invitation } from "@/types/api";

const PAGE_SIZE = 25;

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "outstanding", label: "Outstanding" },
  { value: "accepted", label: "Accepted" },
  { value: "revoked", label: "Revoked" },
  { value: "expired", label: "Expired" },
];

const STATUS_TONES: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  outstanding: "warning",
  accepted: "success",
  revoked: "danger",
  expired: "neutral",
};

export function InvitationList() {
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const [draftEmail, setDraftEmail] = useState("");
  const [email, setEmail] = useState("");
  const [version, setVersion] = useState(0);

  const { state, reload } = useApiQuery(
    (options) => listInvitations({ limit: PAGE_SIZE, offset, status, email }, options),
    `admin:invitations:${offset}:${status}:${email}:${version}`,
  );

  if (state.status === "loading") {
    return <LoadingState label="Loading invitations" rows={4} />;
  }

  if (state.status === "error") {
    return <ErrorState error={state.error} onRetry={reload} />;
  }

  const invitations = state.data.items;
  const count = state.data.meta.count;

  function applyFilter(nextEmail: string) {
    setOffset(0);
    setEmail(nextEmail);
  }

  function afterMutation() {
    setVersion((value) => value + 1);
  }

  return (
    <div className="stack stack-5">
      <form
        className="row-center"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          applyFilter(draftEmail.trim());
        }}
      >
        <div className="form-field" style={{ flex: "1 1 auto" }}>
          <label className="form-label" htmlFor="invitation-email">
            Email address
          </label>
          <input
            id="invitation-email"
            className="form-control"
            type="email"
            value={draftEmail}
            onChange={(event) => setDraftEmail(event.target.value)}
            placeholder="invitee@example.com"
          />
        </div>

        <div className="form-field" style={{ flex: "0 1 12rem" }}>
          <SelectField
            id="invitation-status"
            label="Status"
            value={status}
            onChange={(value) => {
              setOffset(0);
              setStatus(value);
            }}
            options={STATUS_OPTIONS}
          />
        </div>

        <Button type="submit" variant="technical" size="sm" arrow={false}>
          Filter
        </Button>
      </form>

      {invitations.length === 0 ? (
        <EmptyState
          title="No invitations"
          description="No invitations match this filter yet."
        />
      ) : (
        <Card>
          <ul className="ruled-list">
            {invitations.map((invitation) => (
              <InvitationRow key={invitation.id} invitation={invitation} onChanged={afterMutation} />
            ))}
          </ul>
        </Card>
      )}

      <div className="row-center" style={{ justifyContent: "space-between" }}>
        <Button
          variant="technical"
          size="sm"
          arrow={false}
          disabled={offset === 0}
          onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
        >
          Previous
        </Button>

        <p className="text-caption" aria-live="polite">
          {count === 0 ? "No invitations" : `Showing ${offset + 1}–${offset + invitations.length} of ${count}`}
        </p>

        <Button
          variant="technical"
          size="sm"
          arrow={false}
          disabled={offset + invitations.length >= count}
          onClick={() => setOffset((value) => value + PAGE_SIZE)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

function InvitationRow({
  invitation,
  onChanged,
}: {
  invitation: Invitation;
  onChanged: () => void;
}) {
  const [notice, setNotice] = useState<string | null>(null);

  const resend = useApiMutation<void, unknown>(() => resendInvitation(invitation.id));
  const revoke = useApiMutation<void, unknown>(() => revokeInvitation(invitation.id));

  const busy = resend.state.status === "pending" || revoke.state.status === "pending";
  const failure =
    resend.state.status === "error"
      ? resend.state.error
      : revoke.state.status === "error"
        ? revoke.state.error
        : null;

  const manageable = invitation.status === "outstanding";

  async function handleResend() {
    const result = await resend.mutate();
    if (result) {
      setNotice("A fresh invitation has been sent.");
      onChanged();
    }
  }

  async function handleRevoke() {
    const result = await revoke.mutate();
    if (result) {
      setNotice("Invitation revoked.");
      onChanged();
    }
  }

  return (
    <li className="ruled-item">
      <div className="stack stack-2">
        <span className="row-center" style={{ gap: "var(--space-2)", flexWrap: "wrap" }}>
          <span>{invitation.email}</span>
          <Badge tone={STATUS_TONES[invitation.status] ?? "neutral"}>{invitation.status}</Badge>
          <span className="app-row-meta">{invitation.role}</span>
        </span>

        <span className="app-row-meta">
          Invited {formatDateTime(invitation.created_at)} · Expires{" "}
          {formatDateTime(invitation.expires_at)}
        </span>

        {failure ? <FormError error={failure} /> : null}
        {notice ? (
          <p className="text-caption" role="status">
            {notice}
          </p>
        ) : null}

        {manageable ? (
          <div className="form-actions">
            <Button
              variant="technical"
              size="sm"
              arrow={false}
              loading={resend.state.status === "pending"}
              loadingLabel="Resending"
              disabled={busy || notice !== null}
              onClick={() => void handleResend()}
            >
              Resend
            </Button>
            <Button
              variant="technical"
              size="sm"
              arrow={false}
              loading={revoke.state.status === "pending"}
              loadingLabel="Revoking"
              disabled={busy || notice !== null}
              onClick={() => void handleRevoke()}
            >
              Revoke
            </Button>
          </div>
        ) : null}
      </div>
    </li>
  );
}
