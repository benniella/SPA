import type { Metadata } from "next";

import { CookiePreferencesCard } from "@/components/consent/cookie-consent";
import { DocumentPage } from "@/components/marketing/document-page";
import { COOKIES } from "@/data/public-pages";

export const metadata: Metadata = {
  title: "Cookies",
  description:
    "How SPA uses cookies and browser storage, and where to manage the preferences that apply to this device.",
  alternates: { canonical: "/cookies" },
  openGraph: {
    url: "/cookies",
    title: "Cookies · SPA",
    description: "How SPA uses cookies and browser storage.",
  },
  robots: { index: false, follow: true },
};

export default function CookiesPage() {
  return (
    <DocumentPage
      id="cookies-headline"
      eyebrow={COOKIES.eyebrow}
      heading={COOKIES.heading}
      lede={COOKIES.lede}
      effectiveDate={COOKIES.effectiveDate}
      notice={COOKIES.notice}
      sections={COOKIES.sections}
    >
      <CookiePreferencesCard />
    </DocumentPage>
  );
}
