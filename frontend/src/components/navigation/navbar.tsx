"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { BrandMark } from "@/components/brand/brand-mark";
import { Icon } from "@/components/ui/icon";
import { ButtonLink } from "@/components/ui/button";
import { NAV_ACTIONS, NAV_ITEMS, PUBLIC_ROUTE_FOR } from "@/data/marketing";

/* How far the panel must be dragged upwards before releasing closes it. */
const SWIPE_CLOSE_DISTANCE = 56;

export function Navbar() {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const toggleRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const dragStart = useRef<number | null>(null);
  const pathname = usePathname();

  /** Nav ids are in-page anchors here and routes elsewhere, so one list serves
   * both. Anywhere else, "Platform" becomes '/about'. */
  const isMarketing = pathname === "/";
  const hrefFor = (id: string) => (isMarketing ? `#${id}` : `/${PUBLIC_ROUTE_FOR[id] ?? "about"}`);

  const close = useCallback((returnFocus = true) => {
    setOpen(false);
    if (returnFocus) toggleRef.current?.focus();
  }, []);

  // Escape closes the panel from anywhere, bound only while it is open.
  useEffect(() => {
    if (!open) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") close();
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, close]);

  // Lock the body while the panel is open, restoring the previous value rather
  // than resetting to "": another component may have set it.
  useEffect(() => {
    if (!open) return;

    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  // Focus the first link when the panel opens, so the next Tab lands inside it
  // rather than continuing through the header behind it. The panel is portalled
  // to the body, so the ref is only populated once it has mounted.
  useEffect(() => {
    if (!open) return;
    const first = panelRef.current?.querySelector<HTMLElement>("a, button");
    first?.focus();
  }, [open]);

  // A swipe upwards on the panel closes it, which is the gesture a thumb reaches
  // for on a phone. The distance is tracked on move and on release: a browser can
  // cancel a touch drag with 'pointercancel' before it fires 'pointerup', so
  // acting on the move keeps the gesture working on a real touchscreen.
  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    dragStart.current = event.clientY;
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const start = dragStart.current;
    if (start === null) return;
    if (start - event.clientY >= SWIPE_CLOSE_DISTANCE) {
      dragStart.current = null;
      close(false);
    }
  }

  function handlePointerEnd(event: React.PointerEvent<HTMLDivElement>) {
    const start = dragStart.current;
    dragStart.current = null;
    if (start === null) return;
    if (start - event.clientY >= SWIPE_CLOSE_DISTANCE) close(false);
  }

  return (
    <header className="nav-shell">
      <nav aria-label="Primary" className="container-page">
        <div className="nav-inner">
          <BrandMark asLink variant="full" />

          <ul className="nav-links">
            {NAV_ITEMS.map((item) => (
              <li key={item.id}>
                <a className="nav-link" href={hrefFor(item.id)}>
                  {item.label}
                </a>
              </li>
            ))}
          </ul>

          <div className="nav-actions">
            <ButtonLink
              href={NAV_ACTIONS.signIn.href}
              variant="technical"
              size="sm"
              arrow={false}
              className="spa-button--nav-sign-in"
            >
              {NAV_ACTIONS.signIn.label}
            </ButtonLink>
            <ButtonLink href={NAV_ACTIONS.primary.href} variant="primary" size="sm">
              {NAV_ACTIONS.primary.label}
            </ButtonLink>
          </div>

          <button
            ref={toggleRef}
            type="button"
            className="nav-toggle"
            aria-expanded={open}
            aria-controls={panelId}
            aria-label={open ? "Close navigation menu" : "Open navigation menu"}
            onClick={() => setOpen((value) => !value)}
          >
            <Icon name={open ? "close" : "menu"} size={20} />
          </button>
        </div>

        {open
          ? createPortal(
              <>
                <button
                  type="button"
                  className="nav-mobile-backdrop"
                  aria-label="Dismiss navigation menu"
                  onClick={() => close(false)}
                />
                <div
                  id={panelId}
                  ref={panelRef}
                  className="nav-mobile"
                  onPointerDown={handlePointerDown}
                  onPointerMove={handlePointerMove}
                  onPointerUp={handlePointerEnd}
                  onPointerCancel={handlePointerEnd}
                >
                  <ul>
                    {NAV_ITEMS.map((item) => (
                      <li key={item.id}>
                        <a
                          className="nav-mobile-link"
                          href={hrefFor(item.id)}
                          onClick={() => close(false)}
                        >
                          {item.label}
                          <Icon name="arrow-right" size={18} />
                        </a>
                      </li>
                    ))}
                  </ul>

                  <div className="nav-mobile-actions">
                    <ButtonLink
                      href={NAV_ACTIONS.primary.href}
                      variant="primary"
                      size="lg"
                      block
                      className="spa-button--hero"
                    >
                      {NAV_ACTIONS.primary.label}
                    </ButtonLink>
                    <ButtonLink
                      href={NAV_ACTIONS.signIn.href}
                      variant="technical"
                      size="lg"
                      block
                      arrow={false}
                      className="spa-button--nav-sign-in"
                    >
                      {NAV_ACTIONS.signIn.label}
                    </ButtonLink>
                  </div>
                </div>
              </>,
              document.body,
            )
          : null}
      </nav>
    </header>
  );
}
