"use client";

import Link from "next/link";

import { ButtonLink } from "@/components/ui/button";
import { DataCell, DataRow, DataTable } from "@/components/ui/data-table";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState, PlannedState } from "@/components/ui/states";
import { useOrganizationId } from "@/features/auth/session";
import { useApiQuery } from "@/hooks/use-api-query";
import { formatDateTime } from "@/lib/format";
import { listReports } from "@/services/reports";
import type { ReportStatus } from "@/types/api";

const MAX_PAGE = 200;

const REPORT_STATUS_LABELS: Record<ReportStatus, string> = {
  draft: "Draft",
  generating: "Generating",
  ready: "Ready",
  failed: "Failed",
};

const REPORT_STATUS_TONE: Record<ReportStatus, "neutral" | "info" | "success" | "danger"> = {
  draft: "neutral",
  generating: "info",
  ready: "success",
  failed: "danger",
};

export function ReportList() {
  const organizationId = useOrganizationId();

  const { state, reload } = useApiQuery(
    (options) => listReports(organizationId ?? "", { limit: MAX_PAGE }, options),
    `reports:${organizationId}`,
    organizationId !== null,
  );

  if (organizationId === null) {
    return (
      <PlannedState
        title="No workspace selected"
        description="Reports belong to an organization. Choose a workspace to see its reports."
      />
    );
  }

  if (state.status === "loading") return <LoadingState label="Loading reports" rows={3} />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={reload} />;

  const reports = state.data.items;

  if (reports.length === 0) {
    return (
      <EmptyState
        icon="analyse"
        title="No reports yet"
        description="A report is a snapshot of an analysis run's metrics and observations, generated from the run itself. Open a completed analysis run to generate one."
        actions={
          <ButtonLink href="/analysis" variant="technical" size="md">
            Go to analysis
          </ButtonLink>
        }
      />
    );
  }

  return (
    <div className="stack stack-4">
      <DataTable
        caption="Reports in this workspace"
        columns={[
          { id: "title", header: "Report" },
          { id: "status", header: "Status" },
          { id: "analysis", header: "Analysis run", secondary: true },
          { id: "generated", header: "Generated", secondary: true },
          { id: "created", header: "Created", secondary: true },
        ]}
      >
        {reports.map((report) => (
          <DataRow key={report.id}>
            <DataCell primary>
              <Link className="app-row-link" href={`/reports/${encodeURIComponent(report.id)}`}>
                {report.title}
              </Link>
            </DataCell>
            <DataCell>
              <span className={`badge badge-${REPORT_STATUS_TONE[report.status]}`}>
                {REPORT_STATUS_LABELS[report.status]}
              </span>
            </DataCell>
            <DataCell secondary>{analysisLabel(report)}</DataCell>
            <DataCell secondary>{formatDateTime(report.generated_at)}</DataCell>
            <DataCell secondary>{formatDateTime(report.created_at)}</DataCell>
          </DataRow>
        ))}
      </DataTable>

      <p className="text-caption">
        {reports.length === 1 ? "1 report" : `${reports.length} reports`} in this workspace.
      </p>
    </div>
  );
}

function analysisLabel(report: {
  analysis_run_id: string | null;
  match_id: string | null;
  team_id: string | null;
}): React.ReactNode {
  if (report.analysis_run_id) {
    return (
      <Link
        className="app-row-link"
        href={`/analysis/${encodeURIComponent(report.analysis_run_id)}`}
      >
        Run {report.analysis_run_id.slice(0, 8)}
      </Link>
    );
  }
  const parts: string[] = [];
  if (report.match_id) parts.push("Match");
  if (report.team_id) parts.push("Team");
  return parts.length > 0 ? parts.join(" · ") : "—";
}
