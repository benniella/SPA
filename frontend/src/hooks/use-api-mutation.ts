"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type MutationState =
  { status: "idle" } | { status: "pending" } | { status: "error"; error: Error };

export interface UseApiMutationResult<TInput, TResult> {
  readonly state: MutationState;
  readonly mutate: (input: TInput) => Promise<TResult | undefined>;
  readonly reset: () => void;
}

export function useApiMutation<TInput, TResult>(
  action: (input: TInput) => Promise<TResult>,
): UseApiMutationResult<TInput, TResult> {
  const [state, setState] = useState<MutationState>({ status: "idle" });

  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const mutate = useCallback(
    async (input: TInput): Promise<TResult | undefined> => {
      setState({ status: "pending" });
      try {
        const result = await action(input);
        if (mounted.current) setState({ status: "idle" });
        return result;
      } catch (error) {
        if (mounted.current) {
          setState({
            status: "error",
            error: error instanceof Error ? error : new Error("The request failed."),
          });
        }
        return undefined;
      }
    },
    [action],
  );

  const reset = useCallback(() => setState({ status: "idle" }), []);

  return { state, mutate, reset };
}
