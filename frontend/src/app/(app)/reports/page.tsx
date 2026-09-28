import type { Metadata } from "next";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { ReportList } from "@/features/reports";

export const metadata: Metadata = {
  title: "Reports",
  description: "Generated performance reports for your SPA workspace.",
  robots: { index: false, follow: false },
};

export default function ReportsPage() {
  return (
    <>
      <AppPageHeader
        title="Reports"
        description="Snapshots of analysis output, generated from an analysis run."
      />
      <AppPageBody>
        <ReportList />
      </AppPageBody>
    </>
  );
}
