const rawApiUrl = process.env.NEXT_PUBLIC_API_URL;
const rawVersionPrefix = process.env.NEXT_PUBLIC_API_VERSION_PREFIX;
const rawWsUrl = process.env.NEXT_PUBLIC_WS_URL;

/* A build without the API configured — a frontend-only preview — must still
   render, so an absent URL empties the base rather than throwing at module
   scope. Requests then fail as ordinary network errors, which the UI already
   reports, instead of taking down every route that imports this module. */
export const config = {
  apiBaseUrl: (rawApiUrl ?? "").trim().replace(/\/+$/, ""),
  apiVersionPrefix: (rawVersionPrefix ?? "/api/v1").replace(/\/+$/, ""),
  wsUrl: rawWsUrl?.trim().replace(/\/+$/, "") ?? "",
} as const;

export const apiConfigured = config.apiBaseUrl !== "";

export function apiUrl(path: string): string {
  if (!apiConfigured) return "";
  const normalised = path.startsWith("/") ? path : `/${path}`;
  return `${config.apiBaseUrl}${config.apiVersionPrefix}${normalised}`;
}
