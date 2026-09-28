import type { Metadata } from "next";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { ButtonLink } from "@/components/ui/button";
import { TeamList } from "@/features/teams";

export const metadata: Metadata = {
  title: "Teams",
  description: "The squads in your SPA workspace.",
  robots: { index: false, follow: false },
};

export default function TeamsPage() {
  return (
    <>
      <AppPageHeader
        title="Teams"
        description="Every squad in this workspace, with the sport and season it belongs to."
        actions={
          <ButtonLink href="/teams/new" variant="primary" size="md">
            Create team
          </ButtonLink>
        }
      />
      <AppPageBody>
        <TeamList />
      </AppPageBody>
    </>
  );
}
