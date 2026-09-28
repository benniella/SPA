"use client";

import Link from "next/link";

import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PlannedState } from "@/components/ui/states";
import { useOrganizationId } from "@/features/auth/session";
import { useApiQuery } from "@/hooks/use-api-query";
import { formatDateTime } from "@/lib/format";
import { getReport } from "@/services/reports";

export function ReportDetail({ reportId }: { reportId: string }) {
  const organizationId = useOrganizationId();

  const report = useApiQuery(
    (options) => getReport(reportId, organizationId ?? "", options),
    `report:${organizationId}:${reportId}`,
    organizationId !== null,
  );

  if (organizationId === null) {
    return (
      <PlannedState
        title="No workspace selected"
        description="A report belongs to an organization. Choose a workspace to open it."
      />
    );
  }

  if (report.state.status === "loading") return <LoadingState label="Loading report" rows={4} />;
  if (report.state.status === "error") {
    return <ErrorState error={report.state.error} onRetry={report.reload} />;
  }

  const record = report.state.data;

  return (
    <div className="stack stack-7">
      <div className="detail-grid">
        <div className="stack stack-5">
          <h2 className="heading-subsection">Report</h2>

          <dl className="fact-list">
            <Fact label="Title" value={record.title} />
            <Fact label="Status" value={record.status} />
            <Fact label="Created" value={formatDateTime(record.created_at)} />
            <Fact label="Generated" value={formatDateTime(record.generated_at)} />
            <Fact
              label="Match"
              value={
                record.match_id ? (
                  <Link
                    className="app-row-link"
                    href={`/matches/${encodeURIComponent(record.match_id)}`}
                  >
                    Open fixture
                  </Link>
                ) : (
                  "Not scoped to a match"
                )
              }
            />
            <Fact
              label="Team"
              value={
                record.team_id ? (
                  <Link
                    className="app-row-link"
                    href={`/teams/${encodeURIComponent(record.team_id)}`}
                  >
                    Open team
                  </Link>
                ) : (
                  "Not scoped to a team"
                )
              }
            />
          </dl>

          {record.error_message ? (
            <div className="state-block" data-tone="error" role="alert">
              <h3 className="state-title">Generation failed</h3>
              <p className="state-text">{record.error_message}</p>
            </div>
          ) : null}
        </div>

        <div className="stack stack-4">
          <PlannedState
            title="No document to download"
            description="Opening a report document needs a file to have been rendered and an endpoint that turns its storage key into a download URL. Neither exists, so there is no download control."
            note="Not available yet. This needs reporting."
          />
        </div>
      </div>

      <section aria-labelledby="report-body-heading" className="stack stack-4">
        <h2 id="report-body-heading" className="heading-subsection">
          Contents
        </h2>

        <PlannedState
          title="This report has no contents yet"
          description="A report is designed to carry performance metrics, spatial views and the analysis runs it was built from, frozen at the moment it was generated. Nothing assembles those sections yet, so the body is empty."
          note="Not available yet. This needs reporting and analysis."
        />
      </section>

      <section aria-labelledby="report-provenance-heading" className="stack stack-4">
        <h2 id="report-provenance-heading" className="heading-subsection">
          Provenance
        </h2>

        <PlannedState
          title="Run provenance is not exposed"
          description="A report is designed to name the analysis runs that produced its numbers, so a figure can be traced back to the footage it came from. Those identifiers are not returned yet, so none are shown here."
          note="Not available yet. This needs reporting."
        />
      </section>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="fact">
      <dt className="fact-label">{label}</dt>
      <dd className="fact-value">{value}</dd>
    </div>
  );
}
