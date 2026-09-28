export type ApiErrorCode =
  | "validation_error"
  | "not_found"
  | "conflict"
  | "invalid_state"
  | "permission_denied"
  | "authentication_required"
  | "unsupported_media"
  | "infrastructure_error"
  | "processing_failed"
  | "configuration_error"
  | "internal_error"
  | "http_error";

interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

interface ApiErrorEnvelope {
  error: ApiErrorBody;
}

function hasErrorEnvelope(value: unknown): value is ApiErrorEnvelope {
  if (typeof value !== "object" || value === null) return false;
  const candidate = (value as { error?: unknown }).error;
  if (typeof candidate !== "object" || candidate === null) return false;
  const body = candidate as { code?: unknown; message?: unknown };
  return typeof body.code === "string" && typeof body.message === "string";
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode | (string & {});
  readonly details: Record<string, unknown> | undefined;

  constructor(
    status: number,
    code: ApiErrorCode | (string & {}),
    message: string,
    details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Whether retrying the same request could plausibly succeed. */
  get isRetryable(): boolean {
    return this.status >= 500 || this.status === 429;
  }

  get isUnauthenticated(): boolean {
    return this.code === "authentication_required";
  }

  get fieldErrors(): Array<{ location: string[]; message: string }> {
    const errors = this.details?.["errors"];
    if (!Array.isArray(errors)) return [];
    return errors.flatMap((entry) => {
      if (typeof entry !== "object" || entry === null) return [];
      const record = entry as { location?: unknown; message?: unknown };
      if (!Array.isArray(record.location) || typeof record.message !== "string") return [];
      return [{ location: record.location.map(String), message: record.message }];
    });
  }
}

export class NetworkError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "NetworkError";
  }
}

export async function toApiError(response: Response): Promise<ApiError> {
  let payload: unknown = undefined;
  try {
    payload = await response.json();
  } catch {
    return new ApiError(
      response.status,
      response.status === 404 ? "not_found" : "http_error",
      response.statusText || `Request failed with status ${response.status}`,
    );
  }

  if (hasErrorEnvelope(payload)) {
    return new ApiError(
      response.status,
      payload.error.code,
      payload.error.message,
      payload.error.details,
    );
  }

  return new ApiError(
    response.status,
    "http_error",
    `Request failed with status ${response.status}`,
  );
}
