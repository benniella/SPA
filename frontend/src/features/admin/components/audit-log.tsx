"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { formatDateTime } from "@/lib/format";
import { listAuditEvents } from "@/services/admin";
import { useApiQuery } from "@/hooks/use-api-query";
import type { AuditEvent } from "@/types/api";

const PAGE_SIZE = 25;

export function AuditLog() {
  const [offset, setOffset] = useState(0);
  const [eventType, setEventType] = useState("");
  const [draftType, setDraftType] = useState("");

  const { state, reload } = useApiQuery(
    (options) => listAuditEvents({ limit: PAGE_SIZE, offset, event_type: eventType }, options),
    `admin:audit:${offset}:${eventType}`,
  );

  if (state.status === "loading") {
    return <LoadingState label="Loading audit events" rows={5} />;
  }

  if (state.status === "error") {
    return <ErrorState error={state.error} onRetry={reload} />;
  }

  const events = state.data.items;
  const count = state.data.meta.count;

  return (
    <div className="stack stack-5">
      <form
        className="row-center"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          setOffset(0);
          setEventType(draftType.trim());
        }}
      >
        <div className="form-field" style={{ flex: "1 1 auto" }}>
          <label className="form-label" htmlFor="audit-event-type">
            Event type
          </label>
          <input
            id="audit-event-type"
            className="form-control"
            value={draftType}
            onChange={(event) => setDraftType(event.target.value)}
            placeholder="e.g. ADMIN_SUSPENDED"
          />
        </div>
        <Button type="submit" variant="technical" size="sm" arrow={false}>
          Filter
        </Button>
      </form>

      {events.length === 0 ? (
        <EmptyState
          title="No audit events"
          description="No administrative events match this filter yet."
        />
      ) : (
        <Card>
          <ul className="ruled-list">
            {events.map((event) => (
              <AuditRow key={event.id} event={event} />
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
          {count === 0
            ? "No events on this page"
            : `Showing ${offset + 1}–${offset + events.length}`}
        </p>

        <Button
          variant="technical"
          size="sm"
          arrow={false}
          disabled={events.length < PAGE_SIZE}
          onClick={() => setOffset((value) => value + PAGE_SIZE)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

function AuditRow({ event }: { event: AuditEvent }) {
  return (
    <li className="ruled-item">
      <span className="stack stack-1">
        <span className="row-center" style={{ gap: "var(--space-2)" }}>
          <Badge tone="info">{event.event_type}</Badge>
        </span>
        <span className="app-row-meta">
          {event.actor_id ? `Actor ${event.actor_id}` : "System"} ·{" "}
          {formatDateTime(event.created_at)}
        </span>
        <AuditMetadata metadata={event.metadata} />
      </span>
    </li>
  );
}

/* Only the flat, scalar entries are shown. Nested structures are summarised
   rather than rendered wholesale, so an audit payload cannot smuggle a secret
   or an unbounded blob into the page. */
function AuditMetadata({ metadata }: { metadata: Record<string, unknown> }) {
  const entries = Object.entries(metadata).filter(
    ([, value]) => value === null || ["string", "number", "boolean"].includes(typeof value),
  );

  if (entries.length === 0) return null;

  return (
    <span className="app-row-meta">
      {entries.map(([key, value]) => `${key}: ${String(value)}`).join(" · ")}
    </span>
  );
}
