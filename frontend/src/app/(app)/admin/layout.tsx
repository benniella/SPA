"use client";

import { usePathname } from "next/navigation";

import { AdminSessionProvider } from "@/features/admin";
import { RequireAdmin } from "@/features/admin";
import { isInvitationPath } from "@/data/admin-navigation";

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
