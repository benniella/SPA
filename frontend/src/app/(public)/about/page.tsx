import type { Metadata } from "next";

import { DocumentPage } from "@/components/marketing/document-page";
import { ABOUT } from "@/data/public-pages";

export const metadata: Metadata = {
  title: "About",
  description:
    "SPA — Sport Performance Analysis turns sports video into structured performance data. What the platform is, the problem it addresses, and who it is built for.",
  alternates: { canonical: "/about" },
  openGraph: {
    url: "/about",
    title: "About SPA — Sport Performance Analysis",
    description:
      "Sports video is already there. The information inside it is not. How SPA turns footage into measurements for athletes, coaches, analysts and teams.",
  },
};

export default function AboutPage() {
  return (
    <DocumentPage
      id="about-headline"
      eyebrow={ABOUT.eyebrow}
      heading={ABOUT.heading}
      lede={ABOUT.lede}
      sections={ABOUT.sections}
    />
  );
}
