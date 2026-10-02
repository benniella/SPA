"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ADMIN_NAV_ITEMS } from "@/data/admin-navigation";

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AdminSectionNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Administration">
      <ul className="row-center" style={{ gap: "var(--space-4)", listStyle: "none", padding: 0 }}>
        {ADMIN_NAV_ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <li key={item.id}>
              <Link
                className="app-row-link"
                href={item.href}
                data-active={active ? "true" : "false"}
                aria-current={active ? "page" : undefined}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
