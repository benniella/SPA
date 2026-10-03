import type { Metadata } from "next";
import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { AdminSectionNav } from "@/features/admin/components/admin-section-nav";
import { InvitationComposer, InvitationList } from "@/features/admin";

export const metadata: Metadata = {
  title: "Invitations",
  description: "Outstanding platform administrator invitations.",
  robots: { index: false, follow: false },
};

export default function InvitationsPage() {
  return (
    <>
      <AppPageHeader
        title="Invitations"
        description="Invite someone to platform administration. An invitation creates an administrator record that stays inactive until a second factor is enrolled."
        actions={<AdminSectionNav />}
      />
      <AppPageBody>
        <InvitationComposer />
        <InvitationList />
      </AppPageBody>
    </>
  );
}
