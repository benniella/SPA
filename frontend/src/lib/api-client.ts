import { apiUrl, apiConfigured } from "@/lib/config";
import { ApiError, NetworkError, toApiError } from "@/lib/api-errors";

export interface RequestOptions {
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

export interface Paginated<T> {
  items: T[];
  meta: { limit: number; offset: number; count: number };
}

const DEFAULT_TIMEOUT_MS = 30_000;

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const entry = part.trim();
    if (entry.startsWith(prefix)) {
      return decodeURIComponent(entry.slice(prefix.length));
    }
  }
  return null;
}

/* The session cookie is HttpOnly, so the CSRF cookie is the only one the browser
   can read. Echoing it into a header is what lets the API tell a same-site
   request from one an attacker's page caused. */
async function csrfHeaders(method: string): Promise<Record<string, string>> {
  if (!MUTATING_METHODS.has(method.toUpperCase())) return {};
  const token = readCookie("spa_csrf");
  return token ? { "X-CSRF-Token": token } : {};
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options: RequestOptions = {},
): Promise<T> {
  const timeoutController = new AbortController();
  const timeout = setTimeout(() => timeoutController.abort(), DEFAULT_TIMEOUT_MS);

  // Without a configured base, 'fetch("")' would request the current page and
  // fail as malformed JSON. Report the real cause instead.
  if (!apiConfigured) {
    clearTimeout(timeout);
    throw new NetworkError("The SPA API is not configured for this deployment.");
  }

  const signal = options.signal
    ? AbortSignal.any([options.signal, timeoutController.signal])
    : timeoutController.signal;

  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      method,
      signal,
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(await csrfHeaders(method)),
        ...options.headers,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "include",
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") {
      throw cause;
    }
    throw new NetworkError("Could not reach the SPA API.", { cause });
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    throw await toApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function locationOf(response: Response): string | null {
  return response.headers.get("Location");
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => request<T>("GET", path, undefined, options),

  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("POST", path, body, options),

  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("PUT", path, body, options),

  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("PATCH", path, body, options),

  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>("DELETE", path, undefined, options),
} as const;

export { ApiError, NetworkError };
export { locationOf as readLocationHeader };
