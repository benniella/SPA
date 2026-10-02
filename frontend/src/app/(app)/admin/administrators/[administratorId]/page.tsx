import type { Metadata } from "next";
import { AppPageBody, AppPageHeader } from "@/components/app/page-header";
import { ButtonLink } from "@/components/ui/button";
import { AdministratorDetail } from "@/features/admin";

export const metadata: Metadata = {
  title: "Administrator",
  description: "A platform administrator.",
  robots: { index: false, follow: false },
};

export default async function AdministratorPage({
  params,
}: {
  params: Promise<{ administratorId: string }>;
}) {
  const { administratorId } = await params;

  return (
    <>
      <AppPageHeader
        title="Administrator"
        description="The record, its roles, and the actions its lifecycle permits."
        breadcrumb={
          <ButtonLink href="/admin/administrators" variant="technical" size="sm">
            All administrators
          </ButtonLink>
        }
      />
      <AppPageBody>
        <AdministratorDetail administratorId={administratorId} />
      </AppPageBody>
    </>
  );
}
