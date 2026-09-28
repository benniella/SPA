"use client";

import { ApiError, NetworkError } from "@/lib/api-errors";

export interface ErrorCopy {
  readonly title: string;
  readonly description: string;
  readonly retryable: boolean;
  readonly needsSignIn: boolean;
}

const GENERIC: ErrorCopy = {
  title: "Something went wrong",
  description:
    "SPA could not complete that request. Try again, and if it keeps failing the platform status on the dashboard will show whether the API is reachable.",
  retryable: true,
  needsSignIn: false,
};

export function describeError(error: Error): ErrorCopy {
  if (error instanceof NetworkError) {
    return {
      title: "Could not reach SPA",
      description:
        "The API did not respond. That usually means the backend is not running, or this browser cannot reach it.",
      retryable: true,
      needsSignIn: false,
    };
  }

  if (error instanceof ApiError) {
    switch (error.code) {
      case "not_found":
        return {
          title: "Not found",
          description:
            "This does not exist in the workspace you are working in. It may have been removed, or it may belong to another organization.",
          retryable: false,
          needsSignIn: false,
        };
      case "authentication_required":
        return {
          title: "Your session has ended",
          description: "Sign in again to continue where you were.",
          retryable: false,
          needsSignIn: true,
        };
      case "permission_denied":
        return {
          title: "Not permitted",
          description: "Your role in this organization does not allow that action.",
          retryable: false,
          needsSignIn: false,
        };
      case "validation_error":
        return {
          title: "That did not validate",
          description:
            "One or more values were rejected. Check the form for the specific fields and try again.",
          retryable: false,
          needsSignIn: false,
        };
      case "conflict":
        return {
          title: "That conflicts with an existing record",
          description:
            "Something with those details already exists in this workspace — most often a duplicate short name.",
          retryable: false,
          needsSignIn: false,
        };
      case "invalid_state":
        return {
          title: "Not possible in the current state",
          description:
            "The item is in a state that does not allow this action yet. Refresh to see its current state.",
          retryable: false,
          needsSignIn: false,
        };
      case "infrastructure_error":
        return {
          title: "SPA is temporarily unavailable",
          description:
            "A service SPA depends on is not responding. This is on our side, not yours — try again shortly.",
          retryable: true,
          needsSignIn: false,
        };
      default:
        return error.isRetryable ? { ...GENERIC, retryable: true } : GENERIC;
    }
  }

  return GENERIC;
}

/** The underlying detail, shown small and secondary. Never the primary message. */
export function errorDetail(error: Error): string | null {
  if (error instanceof ApiError) {
    return typeof error.message === "string" && error.message.length > 0 ? error.message : null;
  }
  return null;
}
