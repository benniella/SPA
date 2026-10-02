"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { DataCell, DataRow, DataTable } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/states";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { formatDateTime } from "@/lib/format";
import { listAdministrators } from "@/services/admin";
import { useApiQuery } from "@/hooks/use-api-query";
import type { Administrator } from "@/types/api";

const MAX_PAGE = 200;

export function AdministratorList() {
  const { state, reload } = useApiQuery(
    (options) => listAdministrators({ limit: MAX_PAGE }, options),
    "admin:administrators",
  );

  if (state.status === "loading") {
    return <LoadingState label="Loading administrators" rows={4} />;
  }

  if (state.status === "error") {
    return <ErrorState error={state.error} onRetry={reload} />;
  }

  const administrators = state.data.items;

  if (administrators.length === 0) {
    return (
      <EmptyState
        title="No administrators yet"
        description="Invite a platform administrator to give someone access to administration."
      />
    );
  }

  return (
    <div className="stack stack-4">
      <DataTable
        caption="Platform administrators"
        columns={[
          { id: "identity", header: "Administrator" },
          { id: "status", header: "Status" },
          { id: "roles", header: "Roles" },
          { id: "mfa", header: "Second factor" },
          { id: "created", header: "Added", secondary: true },
        ]}
      >
        {administrators.map((administrator) => (
          <DataRow key={administrator.id}>
            <DataCell primary>
              <AdministratorLink administrator={administrator} />
            </DataCell>
            <DataCell>
              <AdministratorStatusBadge status={administrator.status} />
            </DataCell>
            <DataCell>
              {administrator.roles.length === 0 ? (
                <span className="app-row-meta">No roles</span>
              ) : (
                <span>{administrator.roles.join(", ")}</span>
              )}
            </DataCell>
            <DataCell>
              <span className="app-row-meta">
                {administrator.mfa_enrolled ? "Enrolled" : "Not enrolled"}
              </span>
            </DataCell>
            <DataCell secondary>
              <span className="app-row-meta">{formatDateTime(administrator.created_at)}</span>
            </DataCell>
          </DataRow>
        ))}
      </DataTable>

      <p className="text-caption">
        {administrators.length === 1
          ? "1 administrator"
          : `${administrators.length} administrators`}{" "}
        on the platform.
      </p>
    </div>
  );
}

export function AdministratorLink({ administrator }: { administrator: Administrator }) {
  return (
    <Link className="app-row-link" href={`/admin/administrators/${administrator.id}`}>
      {administrator.email ?? administrator.id}
    </Link>
  );
}

const STATUS_TONES: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  active: "success",
  invited: "warning",
  suspended: "warning",
  revoked: "danger",
};

/* The status is carried by the text as well as the tone: an administrator who
   cannot distinguish the colours still has to be able to tell an active account
   from a revoked one. */
export function AdministratorStatusBadge({ status }: { status: string }) {
  const tone = STATUS_TONES[status] ?? "neutral";
  return <Badge tone={tone}>{status}</Badge>;
}
