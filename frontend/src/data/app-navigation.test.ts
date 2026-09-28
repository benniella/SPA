import { describe, expect, it } from "vitest";

import {
  APP_NAV_ITEMS,
  APP_SECONDARY_ITEMS,
  MOBILE_NAV_ITEMS,
  isProtectedPath,
} from "@/data/app-navigation";

describe("protected prefixes", () => {
  it.each([
    "/dashboard",
    "/teams",
    "/players",
    "/matches",
    "/videos",
    "/analysis",
    "/reports",
    "/settings",
    "/account",
  ])("treats %s as an application route", (path) => {
    expect(isProtectedPath(path)).toBe(true);
  });

  it.each([
    "/teams/0f1c2a3b-4d5e-6f70-8192-a3b4c5d6e7f8",
    "/players/abc",
    "/matches/abc/extra",
    "/videos/abc",
    "/analysis/abc",
    "/reports/abc",
  ])("treats the detail route %s as protected", (path) => {
    expect(isProtectedPath(path)).toBe(true);
  });

  it.each([
    "/",
    "/about",
    "/privacy",
    "/terms",
    "/compliance",
    "/security",
    "/contact",
    "/sign-in",
  ])("leaves the public route %s public", (path) => {
    expect(isProtectedPath(path)).toBe(false);
  });

  it("does not treat a lookalike path as protected", () => {
    // A prefix check that uses 'startsWith' without the separator would mark
    // '/teamsheets' as an application route.
    expect(isProtectedPath("/teamsheets")).toBe(false);
    expect(isProtectedPath("/dashboard-archive")).toBe(false);
  });
});

describe("navigation configuration", () => {
  it("covers every protected route in the navigation lists", () => {
    for (const item of [...APP_NAV_ITEMS, ...APP_SECONDARY_ITEMS]) {
      expect(isProtectedPath(item.href)).toBe(true);
    }
  });

  it("keeps the mobile bar to five destinations", () => {
    // The bar is a thumb-reachable row, not a scrolling menu; more than five
    // destinations would not fit a 320px viewport without horizontal scrolling.
    expect(MOBILE_NAV_ITEMS.length).toBeLessThanOrEqual(5);
    expect(MOBILE_NAV_ITEMS.length).toBeGreaterThan(0);
  });

  it("gives every mobile item a matching primary nav entry", () => {
    // The bar is a filter of the primary list, not a second list. A divergence here
    // would mean a destination reachable on one viewport and not the other.
    const primaryIds = new Set(APP_NAV_ITEMS.filter((item) => item.primary).map((i) => i.id));
    for (const item of MOBILE_NAV_ITEMS) {
      expect(primaryIds.has(item.id)).toBe(true);
    }
  });

  it("uses unique ids and hrefs", () => {
    const all = [...APP_NAV_ITEMS, ...APP_SECONDARY_ITEMS];
    expect(new Set(all.map((item) => item.id)).size).toBe(all.length);
    expect(new Set(all.map((item) => item.href)).size).toBe(all.length);
  });
});
