import type { Metadata } from "next";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { MatchForm } from "@/features/matches";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Create match",
  robots: { index: false, follow: false },
};

export default function NewMatchPage() {
  return (
    <>
      <AppPageHeader
        title="Create a match"
        description="A fixture names the two sides and the date. Opponents can be entered by name, so they do not need to exist as teams."
        breadcrumb={
          <>
            <Link className="app-row-link" href="/matches">
              Matches
            </Link>
            <span className="breadcrumb-separator" aria-hidden="true">
              /
            </span>
            <span className="breadcrumb-current">New match</span>
          </>
        }
      />
      <AppPageBody>
        <MatchForm />
      </AppPageBody>
    </>
  );
}
