import type { Metadata } from "next";

import { DocumentPage } from "@/components/marketing/document-page";
import { PracticeGrid, PracticeSection } from "@/components/marketing/practice-grid";
import { Banner } from "@/components/ui/banner";
import { SECURITY } from "@/data/public-pages";

export const metadata: Metadata = {
  title: "Security",
  description:
    "The security principles SPA is built on — least privilege, organisation-scoped access and a browser with no database credentials — and how to report a vulnerability.",
  alternates: { canonical: "/security" },
  openGraph: {
    url: "/security",
    title: "Security · SPA",
    description: "The principles SPA is built on, and how to report a vulnerability.",
  },
};

export default function SecurityPage() {
  return (
    <DocumentPage
      id="security-headline"
      eyebrow={SECURITY.eyebrow}
      heading={SECURITY.heading}
      lede={SECURITY.lede}
      sections={SECURITY.sections}
    >
      <div className="page-notice">
        <Banner tone="informational" title="Scope of this page" icon="vision">
          <p>{SECURITY.disclosureNotice}</p>
        </Banner>
      </div>

      <PracticeSection id="principles" heading="Principles and controls">
        <p className="text-body practice-intro">
          Items marked <strong>In place</strong> exist in the current build. Items marked{" "}
          <strong>Planned</strong> are intended and not yet implemented.
        </p>
        <PracticeGrid items={SECURITY.principles} />
      </PracticeSection>

      <PracticeSection id="reporting" heading={SECURITY.reporting.heading}>
        {SECURITY.reporting.paragraphs.map((paragraph) => (
          <p key={paragraph} className="text-body document-paragraph">
            {paragraph}
          </p>
        ))}
        <ul className="document-list">
          {SECURITY.reporting.items.map((item) => (
            <li key={item} className="document-list-item">
              {item}
            </li>
          ))}
        </ul>
        <p className="document-placeholder">
          <span className="text-micro">Open item</span>A private reporting address and a disclosure
          policy are not yet published. The contact address on this site is a placeholder.
        </p>
      </PracticeSection>
    </DocumentPage>
  );
}
