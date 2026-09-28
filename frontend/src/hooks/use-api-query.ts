"use client";

import { useCallback, useEffect, useState } from "react";

import { NetworkError } from "@/lib/api-errors";
import type { RequestOptions } from "@/lib/api-client";

export type QueryState<T> =
  { status: "loading" } | { status: "success"; data: T } | { status: "error"; error: Error };

export interface UseApiQueryResult<T> {
  readonly state: QueryState<T>;
  readonly reload: () => void;
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new NetworkError("Could not reach the SPA API.");
}

export function useApiQuery<T>(
  fetcher: (options: RequestOptions) => Promise<T>,
  key: string,
  enabled = true,
): UseApiQueryResult<T> {
  const [state, setState] = useState<QueryState<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    if (!enabled) return;

    let ignore = false;
    const controller = new AbortController();

    fetcher({ signal: controller.signal })
      .then((data) => {
        if (ignore || controller.signal.aborted) return;
        setState({ status: "success", data });
      })
      .catch((error: unknown) => {
        if (ignore || isAbort(error) || controller.signal.aborted) return;
        setState({ status: "error", error: toError(error) });
      });

    return () => {
      ignore = true;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled, attempt]);

  return { state, reload };
}
