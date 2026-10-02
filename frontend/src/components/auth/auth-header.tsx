"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { BrandMark } from "@/components/brand/brand-mark";
import { Icon } from "@/components/ui/icon";
import type { IconName } from "@/data/marketing";

export interface AuthHeaderLink {
  readonly href: string;
  readonly label: string;
  readonly icon?: IconName;
}

const SHARED_ITEMS: readonly AuthHeaderLink[] = [
  { href: "/help", label: "Help center", icon: "understand" },
];

const SIGN_IN_ITEMS: readonly AuthHeaderLink[] = [
  { href: "/sign-up", label: "Create an account", icon: "user" },
  ...SHARED_ITEMS,
];

const SIGN_UP_ITEMS: readonly AuthHeaderLink[] = [
  { href: "/sign-in", label: "Sign in", icon: "user" },
  ...SHARED_ITEMS,
];

export function AuthHeader({ menuItems }: { menuItems?: readonly AuthHeaderLink[] }) {
  return (
    <header className="auth-header">
      <div className="auth-header__bar">
        <Link
          className="auth-header__brand"
          href="/"
          aria-label="SPA — Sport Performance Analysis, home"
        >
          <BrandMark variant="compact" />
        </Link>

        {menuItems ? <AuthMenu items={menuItems} /> : null}
      </div>
    </header>
  );
}

export function AuthMenu({
  items,
  label = "Account",
}: {
  items: readonly AuthHeaderLink[];
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="auth-menu" ref={rootRef}>
      <button
        type="button"
        className="auth-menu__trigger"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={label}
        onClick={() => setOpen((value) => !value)}
      >
        <Icon name={open ? "chevron-up" : "chevron-down"} size={18} />
      </button>

      {open ? (
        <div id={menuId} className="auth-menu__panel">
          <ul className="auth-menu__list">
            {items.map((item) => (
              <li key={item.href}>
                <Link className="auth-menu__link" href={item.href} onClick={() => setOpen(false)}>
                  {item.icon ? <Icon name={item.icon} size={16} /> : null}
                  <span>{item.label}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export const AUTH_MENU_ITEMS = {
  signIn: SIGN_IN_ITEMS,
  signUp: SIGN_UP_ITEMS,
} as const;
