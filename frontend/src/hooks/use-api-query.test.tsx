import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useApiQuery } from "@/hooks/use-api-query";
import { NetworkError } from "@/lib/api-errors";

describe("useApiQuery", () => {
  it("moves from loading to success", async () => {
    const fetcher = vi.fn().mockResolvedValue({ value: 42 });

    const { result } = renderHook(() => useApiQuery(fetcher, "key-1"));

    expect(result.current.state.status).toBe("loading");
    await waitFor(() => expect(result.current.state.status).toBe("success"));
    expect(result.current.state).toEqual({ status: "success", data: { value: 42 } });
  });

  it("moves to error and keeps the error instance", async () => {
    const failure = new NetworkError("Could not reach the SPA API.");
    const fetcher = vi.fn().mockRejectedValue(failure);

    const { result } = renderHook(() => useApiQuery(fetcher, "key-2"));

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    expect(result.current.state.status === "error" && result.current.state.error).toBe(failure);
  });

  it("does not fetch while disabled", () => {
    const fetcher = vi.fn().mockResolvedValue({});

    const { result } = renderHook(() => useApiQuery(fetcher, "key-3", false));

    expect(fetcher).not.toHaveBeenCalled();
    expect(result.current.state.status).toBe("loading");
  });

  it("re-runs when the key changes", async () => {
    const fetcher = vi.fn().mockResolvedValue({});
    let key = "a";

    const { rerender } = renderHook(() => useApiQuery(fetcher, key));

    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));

    key = "b";
    rerender();

    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  });

  it("re-runs on reload", async () => {
    const fetcher = vi.fn().mockResolvedValue({});

    const { result } = renderHook(() => useApiQuery(fetcher, "key-4"));
    await waitFor(() => expect(result.current.state.status).toBe("success"));

    result.current.reload();

    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  });

  it("passes an abort signal to the fetcher", async () => {
    const fetcher = vi.fn().mockResolvedValue({});
    renderHook(() => useApiQuery(fetcher, "key-5"));

    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    const options = fetcher.mock.calls[0]?.[0] as { signal?: AbortSignal };
    expect(options.signal).toBeInstanceOf(AbortSignal);
  });

  it("treats a cancellation as neither success nor failure", async () => {
    const abort = new DOMException("Aborted", "AbortError");
    const fetcher = vi.fn().mockRejectedValue(abort);

    const { result } = renderHook(() => useApiQuery(fetcher, "key-6"));
    await waitFor(() => expect(fetcher).toHaveBeenCalled());

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(result.current.state.status).toBe("loading");
  });

  it("aborts the in-flight request on unmount", async () => {
    let captured: AbortSignal | undefined;
    const fetcher = vi.fn((options: { signal?: AbortSignal }) => {
      captured = options.signal;
      return new Promise(() => {});
    });

    const { unmount } = renderHook(() => useApiQuery(fetcher, "key-7"));
    await waitFor(() => expect(captured).toBeDefined());

    expect(captured?.aborted).toBe(false);
    unmount();
    expect(captured?.aborted).toBe(true);
  });
});
