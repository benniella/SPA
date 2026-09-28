import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { AnalysisRunDetail } from "@/features/analysis/components/analysis-run-detail";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Analysis run",
  robots: { index: false, follow: false },
};

export default async function AnalysisRunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  if (!isUuid(runId)) notFound();

  return (
    <>
      <AppPageHeader
        title="Analysis run"
        breadcrumb={
          <>
            <Link className="app-row-link" href="/analysis">
              Analysis
            </Link>
            <span className="breadcrumb-separator" aria-hidden="true">
              /
            </span>
            <span className="breadcrumb-current">Run detail</span>
          </>
        }
      />
      <AppPageBody>
        <AnalysisRunDetail runId={runId} />
      </AppPageBody>
    </>
  );
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}
