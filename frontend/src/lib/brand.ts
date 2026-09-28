import type { Metadata } from "next";

export const BRAND_ASSETS = {
  mark: "/assets/logos/spa-mark.svg",
  markLight: "/assets/logos/spa-mark-light.svg",
  faviconSvg: "/assets/logos/favicon.svg",
  icon192: "/assets/logos/spa-mark-192.png",
  icon512: "/assets/logos/spa-mark-512.png",
} as const;

export const BRAND_ICONS: Metadata["icons"] = {
  icon: [
    { url: BRAND_ASSETS.faviconSvg, type: "image/svg+xml" },
    { url: "/assets/logos/favicon-32.png", sizes: "32x32", type: "image/png" },
    { url: "/assets/logos/favicon-16.png", sizes: "16x16", type: "image/png" },
  ],
  shortcut: ["/assets/logos/favicon.ico"],
  apple: [{ url: BRAND_ASSETS.icon192, sizes: "192x192", type: "image/png" }],
};
