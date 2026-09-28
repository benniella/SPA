"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { THEME_ATTRIBUTE, systemTheme } from "@/lib/theme";
import type { ResolvedTheme } from "@/lib/theme";

interface ThemeContextValue {
  readonly resolved: ResolvedTheme;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [resolved, setResolved] = useState<ResolvedTheme>(systemTheme);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;

    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const next = systemTheme();
      setResolved(next);
      document.documentElement.setAttribute(THEME_ATTRIBUTE, next);
      document.documentElement.style.colorScheme = next;
    };

    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, []);

  const value = useMemo(() => ({ resolved }), [resolved]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used inside <ThemeProvider>.");
  }
  return context;
}
