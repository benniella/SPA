"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { listOrganizations } from "@/services/organizations";
import type { Organization } from "@/types/api";

const WORKSPACE_KEY = "spa.dev.workspace";

export type SessionStatus = "loading" | "authenticated" | "unauthenticated";

export interface SessionValue {
  readonly status: SessionStatus;
  readonly organization: Organization | null;
  readonly organizations: readonly Organization[];
  readonly organizationsStatus: "idle" | "loading" | "error";
  readonly selectWorkspace: (organization: Organization) => void;
  readonly signOut: () => void;
  readonly refreshOrganizations: () => void;
}

const SessionContext = createContext<SessionValue | null>(null);

function readStoredId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(WORKSPACE_KEY);
  } catch {
    // A browser with storage disabled (private mode, hardened settings) throws on
    // access rather than returning null. Treating that as "no session" is correct
    // and keeps the application usable.
    return null;
  }
}

function writeStoredId(id: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (id === null) window.localStorage.removeItem(WORKSPACE_KEY);
    else window.localStorage.setItem(WORKSPACE_KEY, id);
  } catch {
    // Ignored deliberately: a failed write degrades to a session that does not
    // survive a reload, which is preferable to a crash on the sign-in page.
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SessionStatus>("loading");
  const [organizations, setOrganizations] = useState<readonly Organization[]>([]);
  const [organizationsStatus, setOrganizationsStatus] = useState<"idle" | "loading" | "error">(
    "loading",
  );
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);

  const refreshOrganizations = useCallback(() => setLoadAttempt((value) => value + 1), []);

  // Resolve the session once on mount: read the stored selection, then confirm it
  // against the API. Confirming matters — a stored id belonging to a workspace
  // that no longer exists would otherwise produce a page of 404s that look like
  // bugs.
  //
  // 'ignore' rather than only an 'AbortController': aborting on cleanup is correct
  // for a single-mount component, but this effect re-runs under two legitimate
  // circumstances — React strict mode's development double-invoke, and an explicit
  // 'refreshOrganizations()' — and in both an abort would cancel a request the re-run
  // then has to repeat. Guarding with a flag stops the *write* without cancelling the
  // read, so a strict-mode remount still resolves the session.
  //
  // The loading transitions are deliberately *not* synchronous 'setState' calls at the
  // top of the effect: React 19's lint rules flag a setState that runs unconditionally
  // before an await, because it makes the effect's first paint depend on a state write
  // rather than on the render that scheduled it. They are set from the async body
  // instead, which is where the transition actually belongs.
  useEffect(() => {
    let ignore = false;

    async function resolve() {
      setOrganizationsStatus("loading");

      let page: { items: Organization[] };
      try {
        page = await listOrganizations({ limit: 50 });
      } catch {
        if (ignore) return;
        setOrganizationsStatus("error");
        // An unreachable API is indistinguishable from "not signed in" for routing
        // purposes, and showing the application would produce a shell full of
        // errors. The sign-in page explains the situation instead.
        setStatus("unauthenticated");
        return;
      }

      if (ignore) return;

      setOrganizations(page.items);
      setOrganizationsStatus("idle");

      const storedId = readStoredId();
      const matched = page.items.find((item) => item.id === storedId) ?? null;

      if (storedId && !matched) writeStoredId(null);

      setOrganization(matched);
      setStatus(matched ? "authenticated" : "unauthenticated");
    }

    void resolve();

    return () => {
      ignore = true;
    };
  }, [loadAttempt]);

  const selectWorkspace = useCallback((next: Organization) => {
    writeStoredId(next.id);
    setOrganization(next);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(() => {
    writeStoredId(null);
    setOrganization(null);
    setStatus("unauthenticated");
  }, []);

  const value = useMemo<SessionValue>(
    () => ({
      status,
      organization,
      organizations,
      organizationsStatus,
      selectWorkspace,
      signOut,
      refreshOrganizations,
    }),
    [
      status,
      organization,
      organizations,
      organizationsStatus,
      selectWorkspace,
      signOut,
      refreshOrganizations,
    ],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used inside <SessionProvider>.");
  }
  return context;
}

export function useOrganizationId(): string | null {
  return useSession().organization?.id ?? null;
}
