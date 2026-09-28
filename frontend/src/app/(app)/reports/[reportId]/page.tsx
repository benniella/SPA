import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { ReportDetail } from "@/features/reports";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Report",
  robots: { index: false, follow: false },
};

export default async function ReportDetailPage({
  params,
}: {
  params: Promise<{ reportId: string }>;
}) {
  const { reportId } = await params;
  if (!isUuid(reportId)) notFound();

  return (
    <>
      <AppPageHeader
        title="Report"
        breadcrumb={
          <>
            <Link className="app-row-link" href="/reports">
              Reports
            </Link>
            <span className="breadcrumb-separator" aria-hidden="true">
              /
            </span>
            <span className="breadcrumb-current">Report detail</span>
          </>
        }
      />
      <AppPageBody>
        <ReportDetail reportId={reportId} />
      </AppPageBody>
    </>
  );
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}
