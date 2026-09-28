import type { Metadata } from "next";

import { DocumentPage } from "@/components/marketing/document-page";
import { PracticeGrid, PracticeSection } from "@/components/marketing/practice-grid";
import { Banner } from "@/components/ui/banner";
import { COMPLIANCE } from "@/data/public-pages";

export const metadata: Metadata = {
  title: "Compliance",
  description:
    "SPA's approach to data protection, access control and the responsible handling of sports and performance data — with current practices distinguished from planned controls.",
  alternates: { canonical: "/compliance" },
  openGraph: {
    url: "/compliance",
    title: "Compliance · SPA",
    description: "Data protection and responsible handling of sports performance data at SPA.",
  },
};

export default function CompliancePage() {
  return (
    <DocumentPage
      id="compliance-headline"
      eyebrow={COMPLIANCE.eyebrow}
      heading={COMPLIANCE.heading}
      lede={COMPLIANCE.lede}
      sections={COMPLIANCE.sections}
    >
      {/* The non-claim, stated before the practices rather than after them. */}
      <div className="page-notice">
        <Banner tone="informational" title="Certifications" icon="detect">
          <p>{COMPLIANCE.certificationNotice}</p>
        </Banner>
      </div>

      <PracticeSection id="practices" heading="Practices and controls">
        <p className="text-body practice-intro">
          Items marked <strong>In place</strong> exist in the current build. Items marked{" "}
          <strong>Planned</strong> are intended and not yet implemented.
        </p>
        <PracticeGrid items={COMPLIANCE.practices} />
      </PracticeSection>
    </DocumentPage>
  );
}
