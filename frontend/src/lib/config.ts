function required(value: string | undefined, name: string): string {
  if (!value || value.trim() === "") {
    throw new Error(
      `Missing required environment variable ${name}. ` +
        "Copy frontend/.env.example to frontend/.env.local and set it.",
    );
  }
  return value.trim();
}

const rawApiUrl = process.env.NEXT_PUBLIC_API_URL;
const rawVersionPrefix = process.env.NEXT_PUBLIC_API_VERSION_PREFIX;
const rawWsUrl = process.env.NEXT_PUBLIC_WS_URL;

export const config = {
  apiBaseUrl: required(rawApiUrl, "NEXT_PUBLIC_API_URL").replace(/\/+$/, ""),
  apiVersionPrefix: (rawVersionPrefix ?? "/api/v1").replace(/\/+$/, ""),
  wsUrl: rawWsUrl?.trim().replace(/\/+$/, "") ?? "",
} as const;

export function apiUrl(path: string): string {
  const normalised = path.startsWith("/") ? path : `/${path}`;
  return `${config.apiBaseUrl}${config.apiVersionPrefix}${normalised}`;
}
