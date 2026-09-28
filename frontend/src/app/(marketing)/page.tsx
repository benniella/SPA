import type { Metadata } from "next";

import { AiEngine } from "@/components/marketing/ai-engine";
import { AudienceSection } from "@/components/marketing/audience-section";
import { CapabilityStrip } from "@/components/marketing/capability-strip";
import { FinalCta } from "@/components/marketing/final-cta";
import { Footer } from "@/components/marketing/footer";
import { Hero } from "@/components/marketing/hero";
import { InsightsSection } from "@/components/marketing/insights-section";
import { MultiSport } from "@/components/marketing/multi-sport";
import { PerformanceSection } from "@/components/marketing/performance-section";
import { ProblemSection } from "@/components/marketing/problem-section";
import { VisualAnalysis } from "@/components/marketing/visual-analysis";
import { MotionScope } from "@/components/motion/primitives";
import { Navbar } from "@/components/navigation/navbar";

export const metadata: Metadata = {
  title: {
    absolute: "SPA — Turn sports video into performance data",
  },
  description:
    "SPA is an AI-powered sports performance analysis platform. Upload sports footage and turn it into structured performance data — detection, tracking, movement analysis and performance metrics for athletes, coaches, teams and analysts.",
  keywords: [
    "sports performance analysis",
    "sports video analysis",
    "athlete tracking",
    "performance analytics",
    "computer vision in sport",
    "movement analysis",
    "coaching analytics",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: "/",
    siteName: "SPA — Sport Performance Analysis",
    title: "SPA — Turn sports video into performance data",
    description:
      "AI-powered performance analysis for athletes, coaches, teams and analysts. Upload your sports footage; SPA detects, tracks and analyses performance.",
    locale: "en_GB",
  },
  twitter: {
    card: "summary_large_image",
    title: "SPA — Turn sports video into performance data",
    description: "AI-powered performance analysis for athletes, coaches, teams and analysts.",
  },
  robots: { index: true, follow: true },
};

const structuredData = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "SPA — Sport Performance Analysis",
  applicationCategory: "SportsApplication",
  description:
    "AI-powered sports performance analysis. Turns sports video into structured performance data through detection, tracking and movement analysis.",
  featureList: [
    "Computer vision detection",
    "Player tracking",
    "Movement analysis",
    "Performance analytics",
    "Multi-sport support",
    "Video analysis",
  ],
} as const;

export default function MarketingPage() {
  return (
    <MotionScope>
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <Navbar />

      <main id="main">
        <Hero />
        <CapabilityStrip />
        <ProblemSection />
        <AiEngine />
        <PerformanceSection />
        <MultiSport />
        <VisualAnalysis />
        <AudienceSection />
        <InsightsSection />
        <FinalCta />
      </main>

      <Footer />

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(structuredData).replace(/</g, "\\u003c"),
        }}
      />
    </MotionScope>
  );
}
