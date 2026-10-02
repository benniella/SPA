import type { Metadata } from "next";
import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { AdminSectionNav } from "@/features/admin/components/admin-section-nav";
import { AuditLog } from "@/features/admin";

export const metadata: Metadata = {
  title: "Administrative audit log",
  description: "Administrative security events.",
  robots: { index: false, follow: false },
};

export default function AuditPage() {
  return (
    <>
      <AppPageHeader
        title="Audit log"
        description="Administrative actions recorded by the platform, newest first."
        actions={<AdminSectionNav />}
      />
      <AppPageBody>
        <AuditLog />
      </AppPageBody>
    </>
  );
}
