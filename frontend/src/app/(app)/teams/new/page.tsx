import type { Metadata } from "next";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { TeamForm } from "@/features/teams";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Create team",
  robots: { index: false, follow: false },
};

export default function NewTeamPage() {
  return (
    <>
      <AppPageHeader
        title="Create a team"
        description="A team is the squad whose players and matches the rest of the workspace is organised around."
        breadcrumb={
          <>
            <Link className="app-row-link" href="/teams">
              Teams
            </Link>
            <span className="breadcrumb-separator" aria-hidden="true">
              /
            </span>
            <span className="breadcrumb-current">New team</span>
          </>
        }
      />
      <AppPageBody>
        <TeamForm />
      </AppPageBody>
    </>
  );
}
