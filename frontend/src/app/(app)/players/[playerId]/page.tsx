import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { PlayerDetail } from "@/features/players";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Player",
  robots: { index: false, follow: false },
};

export default async function PlayerDetailPage({
  params,
}: {
  params: Promise<{ playerId: string }>;
}) {
  const { playerId } = await params;
  if (!isUuid(playerId)) notFound();

  return (
    <>
      <AppPageHeader
        title="Player"
        breadcrumb={
          <>
            <Link className="app-row-link" href="/players">
              Players
            </Link>
            <span className="breadcrumb-separator" aria-hidden="true">
              /
            </span>
            <span className="breadcrumb-current">Player profile</span>
          </>
        }
      />
      <AppPageBody>
        <PlayerDetail playerId={playerId} />
      </AppPageBody>
    </>
  );
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}
