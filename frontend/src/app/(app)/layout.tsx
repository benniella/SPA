"use client";

import { usePathname } from "next/navigation";

import { AppHeader } from "@/components/app/app-header";
import { AppMobileNav, AppSidebar } from "@/components/app/app-navigation";
import { MotionScope } from "@/components/motion/primitives";
import { RequireSession } from "@/features/auth";
import { SessionProvider } from "@/features/auth/session";
import { ProcessingEventsProvider } from "@/features/processing";

export default function AppLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();

  return (
    <SessionProvider>
      <ProcessingEventsProvider>
        <MotionScope>
          <RequireSession from={pathname}>
            <a className="skip-link" href="#application-main">
              Skip to content
            </a>

            <div className="app-shell">
              <AppHeader />
              <AppSidebar />
              <main id="application-main" className="app-main">
                {children}
              </main>
              <AppMobileNav />
            </div>
          </RequireSession>
        </MotionScope>
      </ProcessingEventsProvider>
    </SessionProvider>
  );
}
