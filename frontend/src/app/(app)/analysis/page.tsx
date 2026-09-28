import type { Metadata } from "next";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { AnalysisOverview } from "@/features/analysis";

export const metadata: Metadata = {
  title: "Analysis",
  description: "Video-processing runs and their status in your SPA workspace.",
  robots: { index: false, follow: false },
};

export default function AnalysisPage() {
  return (
    <>
      <AppPageHeader
        title="Analysis"
        description="Where processing runs appear once the detection, tracking and metric pipeline exists."
      />
      <AppPageBody>
        <AnalysisOverview />
      </AppPageBody>
    </>
  );
}
