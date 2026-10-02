import type { Metadata } from "next";
import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { AdminSecurityPanel } from "@/features/admin";

export const metadata: Metadata = {
  title: "Administrative security",
  description: "Enroll or verify your administrative second factor.",
  robots: { index: false, follow: false },
};

export default function AdminSecurityPage() {
  return (
    <>
      <AppPageHeader
        title="Administrative security"
        description="The second factor that protects platform administration."
      />
      <AppPageBody>
        <AdminSecurityPanel />
      </AppPageBody>
    </>
  );
}
