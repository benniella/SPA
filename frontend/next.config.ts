import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,

  allowedDevOrigins: ["127.0.0.1", "192.168.8.104"],

  typescript: {
    ignoreBuildErrors: false,
  },

  poweredByHeader: false,

  compiler: {
    removeConsole: process.env.NODE_ENV === "production" ? { exclude: ["error", "warn"] } : false,
  },

  experimental: {
    optimizePackageImports: ["@/components/ui", "@/components/marketing", "motion"],
  },
};

export default nextConfig;
