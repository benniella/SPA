import type { Metadata } from "next";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { ButtonLink } from "@/components/ui/button";
import { PlayerList } from "@/features/players";

export const metadata: Metadata = {
  title: "Players",
  description: "The athletes registered in your SPA workspace.",
  robots: { index: false, follow: false },
};

export default function PlayersPage() {
  return (
    <>
      <AppPageHeader
        title="Players"
        description="The athletes in this workspace, and where their performance data will be attributed."
        actions={
          <ButtonLink href="/players/new" variant="primary" size="md">
            Add player
          </ButtonLink>
        }
      />
      <AppPageBody>
        <PlayerList />
      </AppPageBody>
    </>
  );
}
