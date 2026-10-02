"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FormError } from "@/components/ui/form";
import { LoadingState } from "@/components/ui/loading-state";
import { formatDateTime } from "@/lib/format";
import { listSecurityEvents, listSessions, revokeAllSessions, revokeSession } from "@/services/auth";
import type { ApiError } from "@/lib/api-client";
import type { SecurityEventRead, SessionSummary } from "@/types/api";

type Loadable<T> =
  | { status: "loading" }
  | { status: "ready"; items: T[] }
  | { status: "error"; error: ApiError };

export function SessionsSection() {
  const [state, setState] = useState<Loadable<SessionSummary>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  const load = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    let ignore = false;

    async function fetchSessions() {
      try {
        const page = await listSessions();
        if (ignore) return;
        setState({ status: "ready", items: page.items });
      } catch (error) {
        if (ignore) return;
        setState({ status: "error", error: error as ApiError });
      }
    }

    void fetchSessions();

    return () => {
      ignore = true;
    };
  }, [attempt]);

  async function revoke(id: string) {
    await revokeSession(id);
    load();
  }

  async function revokeOthers() {
    await revokeAllSessions();
    load();
  }

  return (
    <section aria-labelledby="account-sessions-heading" className="stack stack-4">
      <h2 id="account-sessions-heading" className="heading-subsection">
        Sessions
      </h2>

      {state.status === "loading" ? <LoadingState label="Loading sessions" rows={2} /> : null}

      {state.status === "error" ? <FormError error={state.error} /> : null}

      {state.status === "ready" ? (
        <Card>
          <ul className="ruled-list">
            {state.items.map((session) => (
              <li key={session.id} className="ruled-item">
                <span className="stack stack-1">
                  <span className="data-table-primary">
                    {session.description}
                    {session.current ? " · this device" : ""}
                  </span>
                  <span className="app-row-meta">
                    Last active {formatDateTime(session.last_used_at)} · expires{" "}
                    {formatDateTime(session.expires_at)}
                    {session.network ? ` · ${session.network}` : ""}
                  </span>
                </span>

                {session.current ? null : (
                  <Button
                    variant="technical"
                    size="sm"
                    arrow={false}
                    onClick={() => void revoke(session.id)}
                  >
                    Revoke
                  </Button>
                )}
              </li>
            ))}
          </ul>

          {state.items.length > 1 ? (
            <div className="form-actions" style={{ marginTop: "var(--space-5)" }}>
              <Button variant="technical" size="md" arrow={false} onClick={() => void revokeOthers()}>
                Sign out other sessions
              </Button>
            </div>
          ) : null}
        </Card>
      ) : null}
    </section>
  );
}

export function SecurityActivitySection() {
  const [state, setState] = useState<Loadable<SecurityEventRead>>({ status: "loading" });

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        const page = await listSecurityEvents();
        if (ignore) return;
        setState({ status: "ready", items: page.items });
      } catch (error) {
        if (ignore) return;
        setState({ status: "error", error: error as ApiError });
      }
    }

    void load();

    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section aria-labelledby="account-security-heading" className="stack stack-4">
      <h2 id="account-security-heading" className="heading-subsection">
        Security activity
      </h2>

      {state.status === "loading" ? <LoadingState label="Loading security activity" rows={2} /> : null}

      {state.status === "error" ? <FormError error={state.error} /> : null}

      {state.status === "ready" ? (
        <Card>
          {state.items.length === 0 ? (
            <p className="text-caption">No security activity has been recorded yet.</p>
          ) : (
            <ul className="ruled-list">
              {state.items.map((event) => (
                <li key={event.id} className="ruled-item">
                  <span className="stack stack-1">
                    <span className="data-table-primary">{event.description}</span>
                    <span className="app-row-meta">{formatDateTime(event.created_at)}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      ) : null}
    </section>
  );
}