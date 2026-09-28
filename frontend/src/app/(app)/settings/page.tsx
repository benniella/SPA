import type { Metadata } from "next";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { WorkspaceSettings } from "@/features/organizations";

export const metadata: Metadata = {
  title: "Settings",
  description: "Workspace settings for your SPA organization.",
  robots: { index: false, follow: false },
};

export default function SettingsPage() {
  return (
    <>
      <AppPageHeader
        title="Settings"
        description="The organization this workspace reads from, and where it is configured."
      />
      <AppPageBody>
        <WorkspaceSettings />
      </AppPageBody>
    </>
  );
}
