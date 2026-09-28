"use client";

import { useEffect, useState } from "react";

import { Badge, type BadgeTone } from "@/components/ui/badge";
import { ApiError, NetworkError, api } from "@/lib/api-client";
import type { HealthResponse } from "@/types/api";

type ConnectionState =
  | { kind: "loading" }
  | { kind: "connected"; health: HealthResponse }
  | { kind: "degraded"; health: HealthResponse }
  | { kind: "unreachable"; detail: string };

export function ApiStatusCard() {
  const [state, setState] = useState<ConnectionState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();

    async function check() {
      try {
        const health = await api.get<HealthResponse>("/health/ready", {
          signal: controller.signal,
        });
        setState(
          health.database === "connected"
            ? { kind: "connected", health }
            : { kind: "degraded", health },
        );
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;

        const detail =
          error instanceof ApiError || error instanceof NetworkError
            ? error.message
            : "Unexpected error while contacting the API.";
        setState({ kind: "unreachable", detail });
      }
    }

    void check();
    return () => controller.abort();
  }, []);

  const { tone, label } = describe(state);

  const health = state.kind === "connected" || state.kind === "degraded" ? state.health : null;
  const unreachableDetail = state.kind === "unreachable" ? state.detail : null;

  const apiState = health ? "reachable" : state.kind === "loading" ? "checking" : "unreachable";

  return (
    <section className="card">
      <div className="row-between">
        <div>
          <h2 className="heading-card">Platform status</h2>
          <p className="text-caption" style={{ marginTop: "0.125rem" }}>
            Live check of the API and its PostgreSQL connection.
          </p>
        </div>
        <Badge tone={tone}>{label}</Badge>
      </div>

      <dl className="field-grid">
        <Field label="API" value={apiState} />
        <Field label="Database" value={health?.database ?? "—"} />
        <Field label="Environment" value={health?.environment ?? "—"} />
        <Field label="Version" value={health?.version ?? "—"} />
      </dl>

      {unreachableDetail !== null ? (
        <p className="text-caption" style={{ marginTop: "1rem" }}>
          {unreachableDetail} Start the backend with <code>make backend-dev</code> and ensure{" "}
          <code>NEXT_PUBLIC_API_URL</code> matches its address.
        </p>
      ) : null}
    </section>
  );
}

function describe(state: ConnectionState): { tone: BadgeTone; label: string } {
  switch (state.kind) {
    case "loading":
      return { tone: "neutral", label: "Checking…" };
    case "connected":
      return { tone: "success", label: "Operational" };
    case "degraded":
      return { tone: "warning", label: "Degraded" };
    case "unreachable":
      return { tone: "danger", label: "Unreachable" };
  }
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-label">{label}</dt>
      <dd className="text-value">{value}</dd>
    </div>
  );
}
