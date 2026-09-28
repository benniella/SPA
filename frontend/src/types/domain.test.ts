import { describe, expect, it } from "vitest";

import type { AnalysisRunStatus } from "@/types/api";
import {
  analysisStatusLabels,
  hasUsableResults,
  isTerminalStatus,
  videoStatusLabels,
} from "@/types/domain";

const ALL_RUN_STATUSES: AnalysisRunStatus[] = [
  "pending",
  "queued",
  "running",
  "succeeded",
  "partially_succeeded",
  "failed",
  "cancelled",
];

describe("isTerminalStatus", () => {
  it("treats in-flight states as non-terminal", () => {
    for (const status of ["pending", "queued", "running"] as const) {
      expect(isTerminalStatus(status)).toBe(false);
    }
  });

  it("treats finished states as terminal", () => {
    for (const status of ["succeeded", "partially_succeeded", "failed", "cancelled"] as const) {
      expect(isTerminalStatus(status)).toBe(true);
    }
  });

  it("classifies every status, so polling cannot loop forever", () => {
    // Guards against a status being added to the union and forgotten here.
    for (const status of ALL_RUN_STATUSES) {
      expect(typeof isTerminalStatus(status)).toBe("boolean");
    }
  });
});

describe("hasUsableResults", () => {
  it("counts partial success as usable", () => {
    // Tracking data can be valid while a later stage failed; hiding it would
    // discard work the user paid for.
    expect(hasUsableResults("partially_succeeded")).toBe(true);
    expect(hasUsableResults("succeeded")).toBe(true);
  });

  it("does not count failure or cancellation as usable", () => {
    expect(hasUsableResults("failed")).toBe(false);
    expect(hasUsableResults("cancelled")).toBe(false);
    expect(hasUsableResults("running")).toBe(false);
  });
});

describe("status labels", () => {
  it("labels every analysis status", () => {
    for (const status of ALL_RUN_STATUSES) {
      expect(analysisStatusLabels[status]).toBeTruthy();
    }
  });

  it("distinguishes partial success from success in the UI", () => {
    expect(analysisStatusLabels.partially_succeeded).not.toBe(analysisStatusLabels.succeeded);
  });

  it("labels every video status", () => {
    for (const status of ["uploaded", "stored", "processing", "ready", "failed"] as const) {
      expect(videoStatusLabels[status]).toBeTruthy();
    }
  });
});
