"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { currentUser, logout as logoutRequest } from "@/services/auth";
import type { AuthenticatedUser, AuthenticatedUserOrganization } from "@/types/api";

const WORKSPACE_KEY = "spa.workspace";

export type SessionStatus = "loading" | "authenticated" | "unauthenticated";

export interface SessionValue {
  readonly status: SessionStatus;
  readonly user: AuthenticatedUser | null;
  readonly organization: AuthenticatedUserOrganization | null;
  readonly organizations: readonly AuthenticatedUserOrganization[];
  readonly selectWorkspace: (organization: AuthenticatedUserOrganization) => void;
  readonly signOut: () => Promise<void>;
  readonly refresh: () => void;
}

const SessionContext = createContext<SessionValue | null>(null);

function readStoredWorkspace(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(WORKSPACE_KEY);
  } catch {
    // A browser with storage disabled (private mode, hardened settings) throws on
    // access rather than returning null. Treating that as "no selection" is
    // correct and keeps the application usable.
    return null;
  }
}

function writeStoredWorkspace(id: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (id === null) window.localStorage.removeItem(WORKSPACE_KEY);
    else window.localStorage.setItem(WORKSPACE_KEY, id);
  } catch {
    // Ignored deliberately: a failed write degrades to a selection that does not
    // survive a reload, which is preferable to a crash on the account page.
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SessionStatus>("loading");
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [organization, setOrganization] = useState<AuthenticatedUserOrganization | null>(null);
  const [attempt, setAttempt] = useState(0);

  const refresh = useCallback(() => setAttempt((value) => value + 1), []);

  /* The session is whatever '/auth/me' says it is. Nothing is inferred from
     browser storage: the cookie is HttpOnly, so the API is the only party that
     can answer whether the caller is still signed in, and a revoked or expired
     session resolves to 'unauthenticated' on the next load. */
  useEffect(() => {
    let ignore = false;

    async function resolve() {
      try {
        const authenticated = await currentUser();
        if (ignore) return;

        setUser(authenticated);

        const stored = readStoredWorkspace();
        const matched =
          authenticated.organizations.find((item) => item.id === stored) ??
          authenticated.organizations[0] ??
          null;

        if (matched && matched.id !== stored) writeStoredWorkspace(matched.id);
        setOrganization(matched);
        setStatus("authenticated");
      } catch {
        if (ignore) return;
        // A 401 is the ordinary "not signed in" answer, and an unreachable API is
        // indistinguishable from it for routing purposes. Either way the app must
        // not render a shell it cannot populate.
        setUser(null);
        setOrganization(null);
        setStatus("unauthenticated");
      }
    }

    void resolve();

    return () => {
      ignore = true;
    };
  }, [attempt]);

  const selectWorkspace = useCallback((next: AuthenticatedUserOrganization) => {
    writeStoredWorkspace(next.id);
    setOrganization(next);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logoutRequest();
    } catch {
      // The local session is cleared either way: a sign-out that could not reach
      // the API must not leave the user apparently signed in.
    }
    writeStoredWorkspace(null);
    setUser(null);
    setOrganization(null);
    setStatus("unauthenticated");
  }, []);

  const organizations = useMemo(() => user?.organizations ?? [], [user]);

  const value = useMemo<SessionValue>(
    () => ({
      status,
      user,
      organization,
      organizations,
      selectWorkspace,
      signOut,
      refresh,
    }),
    [status, user, organization, organizations, selectWorkspace, signOut, refresh],
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
