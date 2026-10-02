import Link from "next/link";

import { BrandMark } from "@/components/brand/brand-mark";

const AUTH_LINKS: readonly { readonly href: string; readonly label: string }[] = [
  { href: "/sign-in", label: "Sign in" },
  { href: "/sign-up", label: "Create account" },
  { href: "/forgot-password", label: "Forgot password" },
  { href: "/reset-password", label: "Reset password" },
  { href: "/verify-email", label: "Verify email" },
];

const AUTH_ACTIONS: readonly { readonly href: string; readonly label: string }[] = [
  { href: "/", label: "Back to overview" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
];

export function AuthSidebar() {
  return (
    <aside className="auth-sidebar" aria-label="Authentication">
      <div className="auth-sidebar__brand">
        <BrandMark asLink variant="compact" />
      </div>

      <nav className="auth-sidebar__nav" aria-label="Account">
        <p className="auth-sidebar__heading">Account</p>
        <ul className="auth-sidebar__links">
          {AUTH_LINKS.map((link) => (
            <li key={link.href}>
              <Link className="auth-sidebar__link" href={link.href}>
                {link.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <div className="auth-sidebar__actions">
        {AUTH_ACTIONS.map((action) => (
          <Link key={action.href} className="app-row-link" href={action.href}>
            {action.label}
          </Link>
        ))}
      </div>
    </aside>
  );
}
