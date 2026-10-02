import type { IconName } from "@/data/marketing";

export interface AdminNavItem {
  readonly id: string;
  readonly href: string;
  readonly label: string;
  readonly icon: IconName;
}

export const ADMIN_NAV_ITEMS: readonly AdminNavItem[] = [
  { id: "administrators", href: "/admin/administrators", label: "Administrators", icon: "user" },
  { id: "invitations", href: "/admin/invitations", label: "Invitations", icon: "vision" },
  { id: "audit", href: "/admin/audit", label: "Audit log", icon: "analytics" },
] as const;

export const ADMIN_BASE_PATH = "/admin";

export function isAdminPath(pathname: string): boolean {
  return pathname === ADMIN_BASE_PATH || pathname.startsWith(`${ADMIN_BASE_PATH}/`);
}

export function isInvitationPath(pathname: string): boolean {
  return pathname === "/admin/invitation" || pathname.startsWith("/admin/invitation/");
}
