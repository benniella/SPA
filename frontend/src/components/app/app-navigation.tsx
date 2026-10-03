"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useId, useState } from "react";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";

import { MOTION } from "@/components/motion/primitives";
import { Icon } from "@/components/ui/icon";
import { APP_NAV_ITEMS, APP_SECONDARY_ITEMS } from "@/data/app-navigation";
import type { AppNavItem } from "@/data/app-navigation";

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppSidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const labelId = useId();

  return (
    <nav
      className="app-sidebar"
      aria-labelledby={labelId}
      data-collapsed={collapsed ? "true" : "false"}
    >
      <p id={labelId} className="visually-hidden">
        Application
      </p>

      <ul className="app-sidebar-group">
        {APP_NAV_ITEMS.map((item) => (
          <li key={item.id}>
            <SidebarLink item={item} active={isActive(pathname, item.href)} collapsed={collapsed} />
          </li>
        ))}
      </ul>

      <hr className="app-sidebar-divider" />

      <ul className="app-sidebar-group">
        {APP_SECONDARY_ITEMS.map((item) => (
          <li key={item.id}>
            <SidebarLink item={item} active={isActive(pathname, item.href)} collapsed={collapsed} />
          </li>
        ))}
      </ul>

      <button
        type="button"
        className="app-sidebar-collapse"
        onClick={() => setCollapsed((value) => !value)}
        aria-expanded={!collapsed}
        aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
      >
        <span className="app-sidebar-collapse-icon" aria-hidden="true">
          <Icon name="menu" size={16} />
        </span>
        {!collapsed ? <span className="app-sidebar-collapse-label">Collapse</span> : null}
      </button>
    </nav>
  );
}

function SidebarLink({
  item,
  active,
  collapsed,
}: {
  item: AppNavItem;
  active: boolean;
  collapsed: boolean;
}) {
  return (
    <Link
      href={item.href}
      className="app-nav-link"
      data-active={active ? "true" : "false"}
      aria-current={active ? "page" : undefined}
      {...(collapsed ? { "aria-label": item.label } : {})}
    >
      <Icon name={item.icon} size={16} />
      <span className="app-nav-label" {...(collapsed ? { "aria-hidden": true } : {})}>
        {item.label}
      </span>
    </Link>
  );
}

export function AppMobileNav() {
  const pathname = usePathname();

  return (
    <nav className="app-mobile-nav" aria-label="Application">
      <ul className="app-mobile-nav-list">
        {APP_NAV_ITEMS.filter((item) => item.primary === true).map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <li key={item.id}>
              <Link
                href={item.href}
                className="app-mobile-nav-link"
                data-active={active ? "true" : "false"}
                aria-current={active ? "page" : undefined}
              >
                <Icon name={item.icon} size={18} />
                <span className="app-mobile-nav-label">{item.label}</span>
              </Link>
            </li>
          );
        })}

        <li>
          <MoreSheet />
        </li>
      </ul>
    </nav>
  );
}

function MoreSheet() {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const reduced = useReducedMotion();

  const extra = [...APP_NAV_ITEMS.filter((item) => item.primary !== true), ...APP_SECONDARY_ITEMS];

  return (
    <>
      <button
        type="button"
        className="app-mobile-nav-link"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        <Icon name={open ? "close" : "menu"} size={18} />
        <span className="app-mobile-nav-label">More</span>
      </button>

      <AnimatePresence>
        {open ? (
          <>
            <motion.button
              type="button"
              className="app-mobile-sheet-backdrop"
              aria-label="Close navigation"
              onClick={() => setOpen(false)}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: MOTION.duration.base, ease: MOTION.easeOut }}
            />
            <motion.div
              id={panelId}
              className="app-mobile-sheet"
              initial={reduced ? { opacity: 0 } : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduced ? { opacity: 0 } : { opacity: 0, y: 8 }}
              transition={{ duration: MOTION.duration.base, ease: MOTION.easeOut }}
            >
              <p className="app-mobile-sheet-heading">Application</p>
              <ul>
                {extra.map((item) => (
                  <li key={item.id}>
                    <Link
                      href={item.href}
                      className="app-mobile-sheet-link"
                      onClick={() => setOpen(false)}
                    >
                      <Icon name={item.icon} size={16} />
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </motion.div>
          </>
        ) : null}
      </AnimatePresence>
    </>
  );
}
