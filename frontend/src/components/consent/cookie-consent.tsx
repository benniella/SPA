"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { CheckboxField } from "@/components/ui/checkbox-field";

const STORAGE_KEY = "spa-cookie-consent";
const CONSENT_VERSION = 1;
export const OPEN_COOKIE_PREFERENCES_EVENT = "spa:open-cookie-preferences";

interface StoredConsent {
  readonly version: typeof CONSENT_VERSION;
  readonly essential: true;
  readonly analytics: boolean;
  readonly updatedAt: string;
}

export function CookieConsent() {
  const [storedConsent, setStoredConsent] = useState(readStoredConsent);
  const [mounted, setMounted] = useState(false);
  const [analyticsOverride, setAnalyticsOverride] = useState<boolean | null>(null);
  const [openOverride, setOpenOverride] = useState<boolean | null>(null);
  const [storageWarning, setStorageWarning] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  const analytics = analyticsOverride ?? storedConsent?.analytics ?? false;
  const open = openOverride ?? storedConsent === null;

  useEffect(() => {
    const frame = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    function onOpenPreferences() {
      setAnalyticsOverride(readStoredConsent()?.analytics ?? false);
      setStorageWarning(false);
      setOpenOverride(true);
    }

    window.addEventListener(OPEN_COOKIE_PREFERENCES_EVENT, onOpenPreferences);
    return () => window.removeEventListener(OPEN_COOKIE_PREFERENCES_EVENT, onOpenPreferences);
  }, []);

  useEffect(() => {
    if (!open) return;

    const panel = dialogRef.current;
    if (!panel) return;

    const previousFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusable = panel.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])',
    );
    focusable.item(0)?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        return;
      }

      if (event.key !== "Tab" || focusable.length === 0) return;
      const first = focusable.item(0);
      const last = focusable.item(focusable.length - 1);

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [open]);

  if (!mounted) return null;

  function record(nextAnalytics: boolean) {
    const consent: StoredConsent = {
      version: CONSENT_VERSION,
      essential: true,
      analytics: nextAnalytics,
      updatedAt: new Date().toISOString(),
    };

    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(consent));
      setStorageWarning(false);
      setStoredConsent(consent);
    } catch {
      setStorageWarning(true);
    }

    setAnalyticsOverride(nextAnalytics);
    setOpenOverride(false);
  }

  return (
    <>
      {open ? (
        <div className="consent" data-testid="consent-backdrop">
          <section
            ref={dialogRef}
            className="consent__panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="consent-title"
            aria-describedby="consent-body"
            tabIndex={-1}
          >
            <p className="consent__eyebrow">Privacy controls</p>
            <h2 id="consent-title" className="consent__title">
              Cookies on this device
            </h2>

            <p id="consent-body" className="consent__body">
              SPA uses an essential session cookie to keep you signed in. Theme and consent
              preferences are stored in this browser. No analytics provider is active in this build.
            </p>

            <div className="consent__options" aria-label="Cookie categories">
              <CheckboxField
                id="consent-essential"
                label="Essential storage"
                description="Session, theme, and consent preferences. Required for core site features."
                checked
                disabled
                onChange={() => undefined}
              />
              <CheckboxField
                id="consent-analytics"
                label="Analytics"
                description="Optional preference. Analytics collection is not enabled in this build."
                checked={analytics}
                onChange={setAnalyticsOverride}
              />
            </div>

            {storageWarning ? (
              <p className="consent__storage-warning" role="status">
                This browser could not save your choice. It applies for this visit only.
              </p>
            ) : null}

            <div className="consent__actions">
              <Button variant="primary" size="sm" arrow={false} onClick={() => record(true)}>
                Accept all
              </Button>
              <Button variant="technical" size="sm" arrow={false} onClick={() => record(analytics)}>
                Save preferences
              </Button>
              <Button variant="technical" size="sm" arrow={false} onClick={() => record(false)}>
                Essential only
              </Button>
            </div>

            <p className="consent__note">
              Read the{" "}
              <Link className="app-row-link" href="/cookies">
                cookie statement
              </Link>
              . You can review or change this choice at any time from that page.
            </p>
          </section>
        </div>
      ) : null}

      {storageWarning && !open ? (
        <p className="consent__storage-toast" role="status">
          Cookie preferences will not persist after you leave this page.
        </p>
      ) : null}
    </>
  );
}

export function CookiePreferencesCard() {
  return (
    <section className="consent-management" aria-labelledby="consent-management-title">
      <div>
        <h2 id="consent-management-title" className="heading-card">
          Cookie preferences on this device
        </h2>
        <p className="text-body">
          Review or change optional cookie preferences stored in this browser. Essential storage is
          always active.
        </p>
      </div>
      <Button
        variant="technical"
        size="sm"
        arrow={false}
        onClick={() => window.dispatchEvent(new Event(OPEN_COOKIE_PREFERENCES_EVENT))}
      >
        Manage preferences
      </Button>
    </section>
  );
}

function readStoredConsent(): StoredConsent | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;

    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;

    const record = parsed as Record<string, unknown>;
    const analytics = record.analytics;
    const updatedAt = record.updatedAt ?? record.decidedAt;
    if (typeof analytics !== "boolean" || typeof updatedAt !== "string") return null;

    if (record.version !== undefined && record.version !== CONSENT_VERSION) return null;

    return {
      version: CONSENT_VERSION,
      essential: true,
      analytics,
      updatedAt,
    };
  } catch {
    return null;
  }
}
