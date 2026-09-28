"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";

import { LoadingState } from "@/components/ui/loading-state";
import { useSession } from "@/features/auth/session";
import { isProtectedPath } from "@/data/app-navigation";

export interface RequireSessionProps {
  readonly from: string;
  readonly children: ReactNode;
}

export function RequireSession({ from, children }: RequireSessionProps) {
  const { status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status !== "unauthenticated") return;

    const target = isProtectedPath(from) ? `/sign-in?from=${encodeURIComponent(from)}` : "/sign-in";
    router.replace(target);
  }, [status, from, router]);

  if (status === "loading") {
    return (
      <div className="centered-viewport container-page">
        <LoadingState label="Resolving your session" rows={2} />
      </div>
    );
  }

  if (status === "unauthenticated") {
    // Deliberately nothing: the redirect above is in flight, and rendering the
    // children here for even one frame would defeat the guard.
    return (
      <div className="centered-viewport container-page">
        <LoadingState label="Redirecting to sign in" rows={1} />
      </div>
    );
  }

  return <>{children}</>;
}
