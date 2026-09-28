import "@testing-library/jest-dom/vitest";

import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

if (typeof AbortSignal.any !== "function") {
  AbortSignal.any = function any(signals: AbortSignal[]): AbortSignal {
    const controller = new AbortController();

    const abort = (reason: unknown) => {
      if (!controller.signal.aborted) controller.abort(reason);
    };

    for (const signal of signals) {
      if (signal.aborted) {
        abort(signal.reason);
        break;
      }
      signal.addEventListener("abort", () => abort(signal.reason), { once: true });
    }

    return controller.signal;
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
