"use client";

import { usePathname } from "next/navigation";

import { AdminSessionProvider } from "@/features/admin";
import { RequireAdmin } from "@/features/admin";
import { isInvitationPath } from "@/data/admin-navigation";

/* The invitation acceptance page is not itself an administrative surface: the
   invitee is an ordinary authenticated user until acceptance completes. It only
   needs the session, so the admin boundary is applied to everything else under
   /admin. */
export default function AdminLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();

  if (isInvitationPath(pathname)) {
    return <>{children}</>;
  }

  return (
    <AdminSessionProvider>
      <RequireAdmin from={pathname}>{children}</RequireAdmin>
    </AdminSessionProvider>
  );
}
