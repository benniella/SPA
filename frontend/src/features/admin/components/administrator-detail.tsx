"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FormError } from "@/components/ui/form";
import { LoadingState } from "@/components/ui/loading-state";
import { ErrorState } from "@/components/ui/error-state";
import { AdministratorStatusBadge } from "@/features/admin/components/administrator-list";
import { StatusBadgeList } from "@/features/admin/components/role-display";
import { formatDateTime } from "@/lib/format";
import {
  getAdministrator,
  listAdministratorRoles,
  listPrivileges,
  listRoles,
  reactivateAdministrator,
  revokeAdministrator,
  setAdministratorRoles,
  suspendAdministrator,
} from "@/services/admin";
import { useApiMutation } from "@/hooks/use-api-mutation";
import type { Administrator } from "@/types/api";

type DetailState =
  | { status: "loading" }
  | { status: "ready"; administrator: Administrator; roles: string[] }
  | { status: "error"; error: Error };

export function AdministratorDetail({ administratorId }: { administratorId: string }) {
  const [state, setState] = useState<DetailState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [catalogue, setCatalogue] = useState<{ roles: string[]; privileges: string[] }>({
    roles: [],
    privileges: [],
  });
  const [notice, setNotice] = useState<string | null>(null);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        const administrator = await getAdministrator(administratorId);
        const roles = await listAdministratorRoles(administratorId);
        if (ignore) return;
        setState({ status: "ready", administrator, roles: roles.items });
      } catch (error) {
        if (ignore) return;
        setState({ status: "error", error: error as Error });
      }
    }

    void load();

    return () => {
      ignore = true;
    };
  }, [administratorId, attempt]);

  useEffect(() => {
    let ignore = false;

    async function loadCatalogue() {
      try {
        const [roles, privileges] = await Promise.all([listRoles(), listPrivileges()]);
        if (ignore) return;
        setCatalogue({ roles: roles.items, privileges: privileges.items });
      } catch {
        // The catalogue only feeds the role editor. If it is unavailable the rest
        // of the view still renders from the administrator's own record.
      }
    }

    void loadCatalogue();

    return () => {
      ignore = true;
    };
  }, []);

  if (state.status === "loading") {
    return <LoadingState label="Loading administrator" rows={4} />;
  }

  if (state.status === "error") {
    return <ErrorState error={state.error} onRetry={reload} />;
  }

  const { administrator, roles } = state;

  return (
    <div className="stack stack-8">
      {notice ? (
        <p className="state-text" role="status">
          {notice}
        </p>
      ) : null}

      <section aria-labelledby="admin-identity-heading" className="stack stack-4">
        <h2 id="admin-identity-heading" className="heading-subsection">
          Identity
        </h2>

        <Card>
          <dl className="fact-list">
            <Fact label="Email" value={administrator.email ?? "Account removed"} />
            <Fact label="Status">
              <AdministratorStatusBadge status={administrator.status} />
            </Fact>
            <Fact
              label="Second factor"
              value={administrator.mfa_enrolled ? "Enrolled" : "Not enrolled"}
            />
            <Fact label="Added" value={formatDateTime(administrator.created_at)} />
            <Fact label="Last changed" value={formatDateTime(administrator.updated_at)} />
          </dl>
        </Card>
      </section>

      <RoleAssignment
        key={roles.join(",")}
        administratorId={administratorId}
        heldRoles={roles}
        catalogue={catalogue.roles}
        privileges={administrator.privileges}
        onChanged={(next) => {
          setState({ status: "ready", administrator, roles: next });
          setNotice("Roles updated.");
          reload();
        }}
      />

      <LifecycleActions
        administrator={administrator}
        onChanged={(message) => {
          setNotice(message);
          reload();
        }}
      />
    </div>
  );
}

function RoleAssignment({
  administratorId,
  heldRoles,
  catalogue,
  privileges,
  onChanged,
}: {
  administratorId: string;
  heldRoles: string[];
  catalogue: string[];
  privileges: string[];
  onChanged: (roles: string[]) => void;
}) {
  const [selected, setSelected] = useState<string[]>(heldRoles);

  const { state, mutate } = useApiMutation<{ roles: string[] }, { items: string[] }>((input) =>
    setAdministratorRoles(administratorId, input),
  );

  const saving = state.status === "pending";

  function toggle(role: string) {
    setSelected((current) =>
      current.includes(role) ? current.filter((item) => item !== role) : [...current, role],
    );
  }

  async function handleSave() {
    const result = await mutate({ roles: selected });
    if (result) onChanged(result.items);
  }

  return (
    <section aria-labelledby="admin-roles-heading" className="stack stack-4">
      <h2 id="admin-roles-heading" className="heading-subsection">
        Roles
      </h2>

      <Card>
        {state.status === "error" ? <FormError error={state.error} /> : null}

        <fieldset className="stack stack-3">
          <legend className="form-label">Assigned roles</legend>

          {catalogue.length === 0 ? (
            <p className="text-caption">The role catalogue is unavailable.</p>
          ) : (
            <div className="stack stack-2">
              {catalogue.map((role) => (
                <label
                  key={role}
                  htmlFor={`role-${role}`}
                  className="row-center"
                  style={{ gap: "var(--space-2)" }}
                >
                  <input
                    id={`role-${role}`}
                    type="checkbox"
                    checked={selected.includes(role)}
                    onChange={() => toggle(role)}
                  />
                  <span>{role}</span>
                </label>
              ))}
            </div>
          )}
        </fieldset>

        <div className="form-actions">
          <Button
            variant="primary"
            size="md"
            arrow={false}
            loading={saving}
            loadingLabel="Saving"
            disabled={catalogue.length === 0}
            onClick={() => void handleSave()}
          >
            Save roles
          </Button>
        </div>

        <div className="stack stack-2" style={{ marginTop: "var(--space-5)" }}>
          <p className="text-label">Effective privileges</p>
          <StatusBadgeList items={privileges} emptyLabel="No privileges" />
        </div>
      </Card>
    </section>
  );
}

function LifecycleActions({
  administrator,
  onChanged,
}: {
  administrator: Administrator;
  onChanged: (message: string) => void;
}) {
  const [confirming, setConfirming] = useState<"revoke" | null>(null);

  const suspend = useApiMutation<void, Administrator>(() => suspendAdministrator(administrator.id));
  const reactivate = useApiMutation<void, Administrator>(() =>
    reactivateAdministrator(administrator.id),
  );
  const revoke = useApiMutation<void, Administrator>(() => revokeAdministrator(administrator.id));

  const busy =
    suspend.state.status === "pending" ||
    reactivate.state.status === "pending" ||
    revoke.state.status === "pending";

  const failure =
    suspend.state.status === "error"
      ? suspend.state.error
      : reactivate.state.status === "error"
        ? reactivate.state.error
        : revoke.state.status === "error"
          ? revoke.state.error
          : null;

  /* Lifecycle actions are chosen from the current status, but this is a UX
     affordance only. The backend validates the transition and answers 409 when
     the state has moved on, which the error block below surfaces. */
  async function handleSuspend() {
    const result = await suspend.mutate();
    if (result) onChanged("Administrator suspended.");
  }

  async function handleReactivate() {
    const result = await reactivate.mutate();
    if (result) onChanged("Administrator reactivated.");
  }

  async function handleRevoke() {
    const result = await revoke.mutate();
    if (result) {
      setConfirming(null);
      onChanged("Administrator revoked.");
    }
  }

  return (
    <section aria-labelledby="admin-lifecycle-heading" className="stack stack-4">
      <h2 id="admin-lifecycle-heading" className="heading-subsection">
        Lifecycle
      </h2>

      <Card>
        {failure ? <FormError error={failure} /> : null}

        <p className="text-body">
          Suspension is reversible and stops administrative access immediately. Revocation is
          permanent.
        </p>

        <div className="form-actions" style={{ marginTop: "var(--space-5)" }}>
          {administrator.status === "active" ? (
            <Button
              variant="technical"
              size="md"
              arrow={false}
              disabled={busy}
              onClick={() => void handleSuspend()}
            >
              {suspend.state.status === "pending" ? "Suspending…" : "Suspend"}
            </Button>
          ) : null}

          {administrator.status === "suspended" ? (
            <Button
              variant="technical"
              size="md"
              arrow={false}
              disabled={busy}
              onClick={() => void handleReactivate()}
            >
              {reactivate.state.status === "pending" ? "Reactivating…" : "Reactivate"}
            </Button>
          ) : null}

          {administrator.status !== "revoked" ? (
            <Button
              variant="primary"
              size="md"
              arrow={false}
              disabled={busy}
              onClick={() => setConfirming("revoke")}
            >
              Revoke
            </Button>
          ) : (
            <p className="text-caption">This administrator has been revoked.</p>
          )}
        </div>

        {confirming === "revoke" ? (
          <div
            className="state-block"
            data-tone="error"
            role="alertdialog"
            aria-label="Confirm revocation"
            style={{ marginTop: "var(--space-5)" }}
          >
            <h3 className="state-title">Revoke this administrator?</h3>
            <p className="state-text">
              Revocation is permanent and cannot be undone. They will lose administrative access
              immediately.
            </p>
            <div className="state-actions">
              <Button
                variant="primary"
                size="md"
                arrow={false}
                loading={revoke.state.status === "pending"}
                loadingLabel="Revoking"
                onClick={() => void handleRevoke()}
              >
                Yes, revoke
              </Button>
              <Button
                variant="technical"
                size="md"
                arrow={false}
                disabled={busy}
                onClick={() => setConfirming(null)}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : null}
      </Card>
    </section>
  );
}

function Fact({
  label,
  value,
  children,
}: {
  label: string;
  value?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="fact">
      <dt className="fact-label">{label}</dt>
      <dd className="fact-value">{value ?? children}</dd>
    </div>
  );
}
