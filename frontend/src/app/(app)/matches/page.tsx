import type { Metadata } from "next";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { ButtonLink } from "@/components/ui/button";
import { MatchList } from "@/features/matches";

export const metadata: Metadata = {
  title: "Matches",
  description: "The fixtures recorded in your SPA workspace.",
  robots: { index: false, follow: false },
};

export default function MatchesPage() {
  return (
    <>
      <AppPageHeader
        title="Matches"
        description="Fixtures are what video, analysis and reports attach to."
        actions={
          <ButtonLink href="/matches/new" variant="primary" size="md">
            Create match
          </ButtonLink>
        }
      />
      <AppPageBody>
        <MatchList />
      </AppPageBody>
    </>
  );
}
