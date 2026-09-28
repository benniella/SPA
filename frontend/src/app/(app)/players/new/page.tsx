import type { Metadata } from "next";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { PlayerForm } from "@/features/players";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Add player",
  robots: { index: false, follow: false },
};

export default function NewPlayerPage() {
  return (
    <>
      <AppPageHeader
        title="Add a player"
        description="A player belongs to the workspace. Squad registration is a separate, dated step."
        breadcrumb={
          <>
            <Link className="app-row-link" href="/players">
              Players
            </Link>
            <span className="breadcrumb-separator" aria-hidden="true">
              /
            </span>
            <span className="breadcrumb-current">New player</span>
          </>
        }
      />
      <AppPageBody>
        <PlayerForm />
      </AppPageBody>
    </>
  );
}
