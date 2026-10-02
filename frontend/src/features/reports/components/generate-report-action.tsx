"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useOrganizationId } from "@/features/auth/session";
import { ApiError } from "@/lib/api-errors";
import { createRunReport } from "@/services/reports";

export function GenerateReportAction({ runId }: { runId: string }) {
  const router = useRouter();
  const organizationId = useOrganizationId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (organizationId === null) return null;

  function generate() {
    setError(null);
    setBusy(true);
    void createRunReport(runId, organizationId ?? "")
      .then((report) => router.push(`/reports/${encodeURIComponent(report.id)}`))
      .catch((cause: unknown) => {
        setError(
          cause instanceof ApiError ? cause.message : "A report could not be requested for this run.",
        );
      })
      .finally(() => setBusy(false));
  }

  return (
    <div className="stack stack-3">
      <div>
        <Button variant="primary" size="md" loading={busy} onClick={generate}>
          {busy ? "Requesting…" : "Generate report"}
        </Button>
      </div>
      {error ? (
        <p className="text-caption" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
