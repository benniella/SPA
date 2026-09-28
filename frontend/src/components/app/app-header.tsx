"use client";

import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";

import { BrandMark } from "@/components/brand/brand-mark";
import { MOTION } from "@/components/motion/primitives";
import { Badge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { APP_NAV_ITEMS, APP_SECONDARY_ITEMS } from "@/data/app-navigation";
import { useSession } from "@/features/auth/session";
import type { Organization } from "@/types/api";

/** The label for the current route, derived from the navigation list so the
 * header cannot disagree with the sidebar. */
function usePageLabel(): string {
  const pathname = usePathname();
  const all = [...APP_NAV_ITEMS, ...APP_SECONDARY_ITEMS];
  const match = all.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
  return match?.label ?? "SPA";
}

export function AppHeader() {
  const { organization, organizations, selectWorkspace, signOut, refreshOrganizations } =
    useSession();
  const pageLabel = usePageLabel();

  return (
    <header className="app-topbar">
      <div className="app-topbar-start">
        <LinkSlot />
        <div className="app-topbar-title">
          <p className="page-context page-context-name">
            {organization?.name ?? "No workspace"}
          </p>
          <p className="app-topbar-page">{pageLabel}</p>
        </div>
      </div>

      <div className="app-topbar-end">
        <EnvironmentBadge />

        <WorkspaceMenu
          organizationName={organization?.name ?? null}
          organizations={organizations}
          onSelect={selectWorkspace}
          onRefresh={refreshOrganizations}
        />

        <AccountMenu onSignOut={signOut} />
      </div>
    </header>
  );
}

/** The brand, linking to the dashboard rather than the marketing site: inside the
 * application, "home" is the dashboard. */
function LinkSlot() {
  return (
    <div className="app-topbar-brand">
      <BrandMark variant="compact" />
    </div>
  );
}

function EnvironmentBadge() {
  if (process.env.NODE_ENV === "production") return null;

  return (
    <span className="app-topbar-env" title="Sign-in is not available yet.">
      <Badge tone="warning">Development session</Badge>
    </span>
  );
}

/* Workspace selector */

function WorkspaceMenu({
  organizationName,
  organizations,
  onSelect,
  onRefresh,
}: {
  organizationName: string | null;
  organizations: readonly Organization[];
  onSelect: (organization: Organization) => void;
  onRefresh: () => void;
}) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const ref = useRef<HTMLDivElement>(null);

  useDismiss(ref, () => setOpen(false), open);

  return (
    <div className="app-menu" ref={ref}>
      <button
        type="button"
        className="app-menu-trigger"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="app-menu-trigger-label">
          <span className="text-micro">Workspace</span>
          <span className="app-menu-trigger-value">{organizationName ?? "None selected"}</span>
        </span>
        <span aria-hidden="true">
          <Icon name="arrow-down" size={14} />
        </span>
      </button>

      <AnimatePresence>
        {open ? (
          <MenuSurface id={menuId} onClose={() => setOpen(false)}>
            {organizations.length === 0 ? (
              <p className="app-menu-empty">
                No organizations exist yet. Create one to start a workspace.
              </p>
            ) : (
              <ul className="app-menu-list">
                {organizations.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className="app-menu-item"
                      data-active={item.name === organizationName ? "true" : undefined}
                      onClick={() => {
                        onSelect(item);
                        setOpen(false);
                      }}
                    >
                      <span>{item.name}</span>
                      <span className="text-micro app-menu-item-slug">{item.slug}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <div className="app-menu-footer">
              <ButtonLink
                href="/settings"
                variant="technical"
                size="sm"
                onClick={() => setOpen(false)}
              >
                Workspace settings
              </ButtonLink>
              <Button variant="technical" size="sm" arrow={false} onClick={onRefresh}>
                Refresh
              </Button>
            </div>
          </MenuSurface>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

/* Account menu */

function AccountMenu({ onSignOut }: { onSignOut: () => void }) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const ref = useRef<HTMLDivElement>(null);

  useDismiss(ref, () => setOpen(false), open);

  return (
    <div className="app-menu" ref={ref}>
      <button
        type="button"
        className="app-menu-trigger app-menu-trigger--icon"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label="Account"
        onClick={() => setOpen((value) => !value)}
      >
        <Icon name="user" size={16} />
      </button>

      <AnimatePresence>
        {open ? (
          <MenuSurface id={menuId} onClose={() => setOpen(false)}>
            <div className="app-menu-header">
              <p className="text-label">Signed in as</p>
              <p className="app-menu-empty">
                No identity record is attached to this session. Accounts, credentials and roles
                are not available yet.
              </p>
            </div>

            <ul className="app-menu-list">
              <li>
                <ButtonLink
                  href="/account"
                  variant="technical"
                  size="sm"
                  block
                  arrow={false}
                  onClick={() => setOpen(false)}
                >
                  Account
                </ButtonLink>
              </li>
              <li>
                <ButtonLink
                  href="/settings"
                  variant="technical"
                  size="sm"
                  block
                  arrow={false}
                  onClick={() => setOpen(false)}
                >
                  Settings
                </ButtonLink>
              </li>
            </ul>

            <div className="app-menu-footer">
              <ButtonLink
                href="/account"
                variant="technical"
                size="sm"
                block
                arrow={false}
                onClick={onSignOut}
              >
                Sign out
              </ButtonLink>
            </div>
          </MenuSurface>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

/* Shared menu surface */

function MenuSurface({
  id,
  onClose,
  children,
}: {
  id: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const reduced = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);

  // Move focus into the surface so a keyboard user is not left behind on a button
  // whose panel has just appeared below them.
  useEffect(() => {
    ref.current?.querySelector<HTMLElement>("a, button")?.focus();
  }, []);

  return (
    <motion.div
      id={id}
      ref={ref}
      className="app-menu-surface"
      initial={reduced ? { opacity: 0 } : { opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={reduced ? { opacity: 0 } : { opacity: 0, y: -4 }}
      transition={{ duration: MOTION.duration.fast, ease: MOTION.easeOut }}
      onKeyDown={(event) => {
        if (event.key === "Escape") onClose();
      }}
    >
      {children}
    </motion.div>
  );
}

/* Close on Escape or on a click outside. */
function useDismiss(ref: React.RefObject<HTMLElement | null>, close: () => void, open: boolean) {
  useEffect(() => {
    if (!open) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") close();
    }

    function onPointerDown(event: PointerEvent) {
      const node = ref.current;
      if (node && event.target instanceof Node && !node.contains(event.target)) close();
    }

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [ref, close, open]);
}
