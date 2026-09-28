import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { MatchDetail } from "@/features/matches";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Match",
  robots: { index: false, follow: false },
};

export default async function MatchDetailPage({
  params,
}: {
  params: Promise<{ matchId: string }>;
}) {
  const { matchId } = await params;
  if (!isUuid(matchId)) notFound();

  return (
    <>
      <AppPageHeader
        title="Match"
        breadcrumb={
          <>
            <Link className="app-row-link" href="/matches">
              Matches
            </Link>
            <span className="breadcrumb-separator" aria-hidden="true">
              /
            </span>
            <span className="breadcrumb-current">Match detail</span>
          </>
        }
      />
      <AppPageBody>
        <MatchDetail matchId={matchId} />
      </AppPageBody>
    </>
  );
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}
