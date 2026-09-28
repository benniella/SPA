import type { Metadata } from "next";

import { DocumentPage } from "@/components/marketing/document-page";
import { PRIVACY } from "@/data/public-pages";

export const metadata: Metadata = {
  title: "Privacy",
  description:
    "How SPA handles account information, sports video and performance data — and which policy decisions are not yet final.",
  alternates: { canonical: "/privacy" },
  openGraph: {
    url: "/privacy",
    title: "Privacy · SPA",
    description: "How SPA handles account information, sports video and performance data.",
  },
  robots: { index: false, follow: true },
};

export default function PrivacyPage() {
  return (
    <DocumentPage
      id="privacy-headline"
      eyebrow={PRIVACY.eyebrow}
      heading={PRIVACY.heading}
      lede={PRIVACY.lede}
      effectiveDate={PRIVACY.effectiveDate}
      notice={PRIVACY.notice}
      sections={PRIVACY.sections}
    />
  );
}
