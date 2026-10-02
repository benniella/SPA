import type { Metadata } from "next";
import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { AccountPanel } from "@/features/auth/components/account-panel";
import {
  EmailSection,
  PasswordSection,
  PhoneSection,
} from "@/features/auth/components/account-sections";
import {
  SecurityActivitySection,
  SessionsSection,
} from "@/features/auth/components/account-security-sections";

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
        description="Your identity, your credentials, your sessions and your security activity."
      />
      <AppPageBody>
        <div className="stack stack-8">
          <AccountPanel />
          <EmailSection />
          <PhoneSection />
          <PasswordSection />
          <SessionsSection />
          <SecurityActivitySection />
        </div>
      </AppPageBody>
    </>
  );
}
