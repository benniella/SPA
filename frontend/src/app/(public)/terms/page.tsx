import type { Metadata } from "next";

import { DocumentPage } from "@/components/marketing/document-page";
import { TERMS } from "@/data/public-pages";

export const metadata: Metadata = {
  title: "Terms",
  description:
    "The intended structure of SPA's terms of service, including which provisions are still open for legal review.",
  alternates: { canonical: "/terms" },
  openGraph: {
    url: "/terms",
    title: "Terms of service · SPA",
    description: "The intended structure of SPA's terms of service.",
  },
  robots: { index: false, follow: true },
};

export default function TermsPage() {
  return (
    <DocumentPage
      id="terms-headline"
      eyebrow={TERMS.eyebrow}
      heading={TERMS.heading}
      lede={TERMS.lede}
      effectiveDate={TERMS.effectiveDate}
      notice={TERMS.notice}
      sections={TERMS.sections}
    />
  );
}
