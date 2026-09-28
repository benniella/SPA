import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SPA — Sport Performance Analysis",
    short_name: "SPA",
    description:
      "Turn sports video into structured performance data for athletes, coaches, teams and analysts.",
    start_url: "/",
    display: "standalone",
    background_color: "#090A0B",
    theme_color: "#090A0B",
    icons: [
      {
        src: "/assets/logos/spa-mark-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/assets/logos/spa-mark-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
    ],
  };
}
