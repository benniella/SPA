import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
    // The API client reads its base URL through 'lib/config.ts', which throws on
    // a missing variable — deliberately, so a misconfigured deployment fails at
    // startup. Tests therefore have to supply one. 'backend/.env.local' is not
    // loaded by Vitest, so it is defined here instead.
    env: {
      NEXT_PUBLIC_API_URL: "http://localhost:8000",
      NEXT_PUBLIC_API_VERSION_PREFIX: "/api/v1",
      NEXT_PUBLIC_WS_URL: "ws://localhost:8000",
    },
    coverage: {
      provider: "v8",
      reportsDirectory: "./coverage",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/test/**", "src/app/**/layout.tsx"],
    },
  },
});
