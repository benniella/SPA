import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { TeamDetail } from "@/features/teams";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Team",
  robots: { index: false, follow: false },
};

export default async function TeamDetailPage({ params }: { params: Promise<{ teamId: string }> }) {
  const { teamId } = await params;

  if (!isUuid(teamId)) notFound();

  return (
    <>
      <AppPageHeader
        title="Team"
        breadcrumb={
          <>
            <Link className="app-row-link" href="/teams">
              Teams
            </Link>
            <span className="breadcrumb-separator" aria-hidden="true">
              /
            </span>
            <span className="breadcrumb-current">Team detail</span>
          </>
        }
      />
      <AppPageBody>
        <TeamDetail teamId={teamId} />
      </AppPageBody>
    </>
  );
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}
