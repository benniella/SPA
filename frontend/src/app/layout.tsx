import type { Metadata, Viewport } from "next";

import { ThemeProvider } from "@/components/theme/theme-provider";
import { BRAND_ICONS } from "@/lib/brand";
import { fontVariables } from "@/lib/fonts";
import { themeScript } from "@/lib/theme";
import "@/styles/globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "SPA — Sport Performance Analysis",
    template: "%s · SPA",
  },
  description:
    "Turn sports video into structured performance data for athletes, coaches, teams and analysts.",
  applicationName: "SPA",
  icons: BRAND_ICONS,
  manifest: "/manifest.webmanifest",
  robots: { index: true, follow: true },
  formatDetection: {
    telephone: false,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  colorScheme: "dark light",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#090A0B" },
    { media: "(prefers-color-scheme: light)", color: "#FFFFFF" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="dark" className={fontVariables} suppressHydrationWarning>
      <head>
        {/* Must run before first paint, so not a 'next/script' with a loading
            strategy. */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
