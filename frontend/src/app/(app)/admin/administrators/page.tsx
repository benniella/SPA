import type { Metadata } from "next";
import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { AdminSectionNav } from "@/features/admin/components/admin-section-nav";
import { AdministratorList } from "@/features/admin";

export const metadata: Metadata = {
  title: "Administrators",
  description: "Platform administrators.",
  robots: { index: false, follow: false },
};

export default function AdministratorsPage() {
  return (
    <>
      <AppPageHeader
        title="Administrators"
        description="Everyone with a platform administration record and the state their access is in."
        actions={<AdminSectionNav />}
      />
      <AppPageBody>
        <AdministratorList />
      </AppPageBody>
    </>
  );
}
