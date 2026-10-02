"use client";

import { useState } from "react";

import { Card } from "@/components/ui/card";
import { Field, FormError, SelectField, apiErrorFor } from "@/components/ui/form";
import { Button } from "@/components/ui/button";
import { createInvitation, listRoles, resendInvitation, revokeInvitation } from "@/services/admin";
import { useApiMutation } from "@/hooks/use-api-mutation";
import { useApiQuery } from "@/hooks/use-api-query";

export function InvitationComposer() {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);

  const catalogue = useApiQuery((options) => listRoles(options), "admin:roles");
  const { state, mutate } = useApiMutation<{ email: string; role: string }, unknown>((input) =>
    createInvitation(input),
  );

  const submitting = state.status === "pending";
  const failure = state.status === "error" ? state.error : null;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = email.trim();
    const result = await mutate({ email: trimmed, role });
    if (result) {
      setSentTo(trimmed);
      setEmail("");
      setRole("");
    }
  }

  const roleOptions =
    catalogue.state.status === "success"
      ? catalogue.state.data.items.map((name) => ({ value: name, label: name }))
      : [];

  return (
    <Card>
      <form className="form" onSubmit={handleSubmit} noValidate>
        {failure ? <FormError error={failure} /> : null}

        {sentTo ? (
          <p className="state-text" role="status">
            Invitation sent to {sentTo}. It stays outstanding until it is accepted or expires.
          </p>
        ) : null}

        <Field
          id="invite-email"
          label="Email address"
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={apiErrorFor(failure, "email")}
        />

        <SelectField
          id="invite-role"
          label="Role"
          required
          value={role}
          onChange={setRole}
          placeholder="Choose a role"
          options={roleOptions}
          hint="The role the invitee holds once their access is activated."
          error={apiErrorFor(failure, "role")}
        />

        <div className="form-actions">
          <Button
            type="submit"
            variant="primary"
            size="md"
            disabled={
              submitting ||
              email.trim() === "" ||
              role === "" ||
              catalogue.state.status !== "success"
            }
          >
            {submitting ? "Sending…" : "Send invitation"}
          </Button>
        </div>
      </form>
    </Card>
  );
}

export function InvitationActions({ invitationId }: { invitationId: string }) {
  const [notice, setNotice] = useState<string | null>(null);

  const resend = useApiMutation<void, unknown>(() => resendInvitation(invitationId));
  const revoke = useApiMutation<void, unknown>(() => revokeInvitation(invitationId));

  const busy = resend.state.status === "pending" || revoke.state.status === "pending";
  const failure =
    resend.state.status === "error"
      ? resend.state.error
      : revoke.state.status === "error"
        ? revoke.state.error
        : null;

  async function handleResend() {
    const result = await resend.mutate();
    if (result) setNotice("A fresh invitation has been sent.");
  }

  async function handleRevoke() {
    const result = await revoke.mutate();
    if (result) setNotice("Invitation revoked.");
  }

  return (
    <div className="stack stack-3">
      {failure ? <FormError error={failure} /> : null}
      {notice ? (
        <p className="text-caption" role="status">
          {notice}
        </p>
      ) : null}

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
    </div>
  );
}
