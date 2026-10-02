"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { resolveAdminAccess } from "@/features/admin/access";
import type { AdminAccessState } from "@/features/admin/access";
import { useSession } from "@/features/auth/session";
import { currentAdministrator } from "@/services/admin";
import type { Administrator } from "@/types/api";

export interface AdminSessionValue {
  readonly status: "loading" | "resolved";
  readonly access: AdminAccessState;
  readonly administrator: Administrator | null;
  readonly refresh: () => void;
}

const AdminSessionContext = createContext<AdminSessionValue | null>(null);

export function AdminSessionProvider({ children }: { children: ReactNode }) {
  const { status: sessionStatus, user } = useSession();
  const [administrator, setAdministrator] = useState<Administrator | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [resolvedAttempt, setResolvedAttempt] = useState<number | null>(null);

  const refresh = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    if (sessionStatus !== "authenticated") return;

    let ignore = false;
    const controller = new AbortController();

    currentAdministrator({ signal: controller.signal })
      .then((admin) => {
        if (ignore) return;
        setAdministrator(admin);
        setError(null);
        setResolvedAttempt(attempt);
      })
      .catch((cause: unknown) => {
        if (ignore || (cause instanceof DOMException && cause.name === "AbortError")) return;
        setAdministrator(null);
        setError(cause instanceof Error ? cause : new Error("The request failed."));
        setResolvedAttempt(attempt);
      });

    return () => {
      ignore = true;
      controller.abort();
    };
  }, [sessionStatus, attempt]);

  /* The provider reports loading until the request for the current attempt has
     either succeeded or been answered with a status the access model understands.
     A request that never settles must not leave the boundary spinning forever. */
  const settled = sessionStatus !== "authenticated" || resolvedAttempt === attempt;

  const access = useMemo<AdminAccessState>(() => {
    if (sessionStatus !== "authenticated") return { state: "anonymous" };
    if (!settled) return { state: "authenticated-non-admin" };
    return resolveAdminAccess({ user, administrator, error });
  }, [sessionStatus, settled, user, administrator, error]);

  const value = useMemo<AdminSessionValue>(
    () => ({
      status: settled ? "resolved" : "loading",
      access,
      administrator,
      refresh,
    }),
    [settled, access, administrator, refresh],
  );

  return <AdminSessionContext.Provider value={value}>{children}</AdminSessionContext.Provider>;
}

export function useAdminSession(): AdminSessionValue {
  const context = useContext(AdminSessionContext);
  if (!context) {
    throw new Error("useAdminSession must be used inside <AdminSessionProvider>.");
  }
  return context;
}
