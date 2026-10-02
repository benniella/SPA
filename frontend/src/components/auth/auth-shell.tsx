import Link from "next/link";
import type { ReactNode } from "react";

import { AUTH_MENU_ITEMS, AuthHeader } from "@/components/auth/auth-header";

export function AuthFooter() {
  return (
    <footer className="auth-footer">
      <div className="auth-footer__notices">
        <Link className="app-row-link" href="/privacy">
          Privacy
        </Link>
        <Link className="app-row-link" href="/terms">
          Terms
        </Link>
      </div>
      <span className="auth-footer__year">© {new Date().getFullYear()} SPA</span>
    </footer>
  );
}

export function AuthPageShell({
  title,
  description,
  menu = "signIn",
  children,
}: {
  title: string;
  description?: string;
  menu?: "signIn" | "signUp";
  children: ReactNode;
}) {
  return (
    <div className="auth-shell">
      <AuthHeader menuItems={AUTH_MENU_ITEMS[menu]} />

      <main id="auth-main" className="auth-body">
        <div className="auth-page-shell stack stack-6">
          <div className="auth-page-heading">
            <h1 className="heading-page">{title}</h1>
            {description ? <p className="auth-page-lede">{description}</p> : null}
          </div>
          {children}
        </div>
      </main>

      <AuthFooter />
    </div>
  );
}
