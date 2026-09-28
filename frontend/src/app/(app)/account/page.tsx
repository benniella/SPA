import type { Metadata } from "next";

import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { AccountPanel } from "@/features/auth/components/account-panel";

export const metadata: Metadata = {
  title: "Account",
  description: "Your SPA account.",
  robots: { index: false, follow: false },
};

export default function AccountPage() {
  return (
    <>
      <AppPageHeader
        title="Account"
        description="Your identity, your session, and what sign-in still has to decide."
      />
      <AppPageBody>
        <AccountPanel />
      </AppPageBody>
    </>
  );
}
