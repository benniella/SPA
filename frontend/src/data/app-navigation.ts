import type { IconName } from "@/data/marketing";

export interface AppNavItem {
  readonly id: string;
  readonly href: string;
  readonly label: string;
  readonly icon: IconName;
  readonly primary?: boolean;
}

export const APP_NAV_ITEMS: readonly AppNavItem[] = [
  { id: "dashboard", href: "/dashboard", label: "Dashboard", icon: "analytics", primary: true },
  { id: "teams", href: "/teams", label: "Teams", icon: "sport", primary: true },
  { id: "players", href: "/players", label: "Players", icon: "motion", primary: true },
  { id: "matches", href: "/matches", label: "Matches", icon: "track", primary: true },
  { id: "videos", href: "/videos", label: "Videos", icon: "video", primary: true },
  { id: "analysis", href: "/analysis", label: "Analysis", icon: "detect" },
  { id: "reports", href: "/reports", label: "Reports", icon: "analyse" },
] as const;

export const APP_SECONDARY_ITEMS: readonly AppNavItem[] = [
  { id: "settings", href: "/settings", label: "Settings", icon: "ai" },
  { id: "account", href: "/account", label: "Account", icon: "vision" },
] as const;

export const MOBILE_NAV_ITEMS: readonly AppNavItem[] = APP_NAV_ITEMS.filter(
  (item) => item.primary === true,
);

export const PROTECTED_PREFIXES: readonly string[] = [
  ...APP_NAV_ITEMS.map((item) => item.href),
  ...APP_SECONDARY_ITEMS.map((item) => item.href),
  "/admin",
] as const;

export function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}
