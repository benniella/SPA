import type { Metadata } from "next";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { ApiStatusCard } from "@/features/analysis";
import { DashboardOverview } from "@/features/dashboard";

export const metadata: Metadata = {
  title: "Dashboard",
  description: "Your SPA performance workspace: teams, players, matches and videos.",
  robots: { index: false, follow: false },
};

export default function DashboardPage() {
  return (
    <>
      <AppPageHeader
        title="Dashboard"
        description="The current state of your performance workspace."
      />
      <AppPageBody>
        <DashboardOverview />
        <ApiStatusCard />
      </AppPageBody>
    </>
  );
}
