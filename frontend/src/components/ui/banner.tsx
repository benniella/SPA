"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useState } from "react";
import type { ReactNode } from "react";

import { MOTION } from "@/components/motion/primitives";
import { Icon } from "@/components/ui/icon";
import type { IconName } from "@/data/marketing";

export type BannerTone = "informational" | "success" | "warning" | "error" | "announcement";

const TONE_ICON: Record<BannerTone, IconName> = {
  informational: "ai",
  success: "check",
  warning: "motion",
  error: "close",
  announcement: "play",
};

const TONE_LABEL: Record<BannerTone, string> = {
  informational: "Information",
  success: "Success",
  warning: "Warning",
  error: "Error",
  announcement: "Announcement",
};

const TONE_ROLE: Record<BannerTone, "status" | "alert"> = {
  informational: "status",
  success: "status",
  warning: "status",
  error: "alert",
  announcement: "status",
};

export interface BannerProps {
  readonly tone?: BannerTone;
  readonly title: ReactNode;
  readonly children?: ReactNode;
  readonly actions?: ReactNode;
  /** Overrides the tone's default icon. */
  readonly icon?: IconName;
  /** Only for banners the user may legitimately close — never a security notice. */
  readonly dismissible?: boolean;
  readonly onDismiss?: () => void;
  readonly className?: string;
}

export function Banner({
  tone = "informational",
  title,
  children,
  actions,
  icon,
  dismissible = false,
  onDismiss,
  className,
}: BannerProps) {
  const [dismissed, setDismissed] = useState(false);
  const reduced = useReducedMotion();

  const dismiss = () => {
    setDismissed(true);
    onDismiss?.();
  };

  return (
    <AnimatePresence initial={false}>
      {dismissed ? null : (
        <motion.div
          className={["banner", `banner-${tone}`, className].filter(Boolean).join(" ")}
          role={TONE_ROLE[tone]}
          aria-label={TONE_LABEL[tone]}
          initial={reduced ? { opacity: 1 } : { opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduced ? { opacity: 0 } : { opacity: 0, height: 0, marginTop: 0 }}
          transition={{ duration: MOTION.duration.base, ease: MOTION.easeOut }}
        >
          <span className="banner-icon" aria-hidden="true">
            <Icon name={icon ?? TONE_ICON[tone]} size={16} />
          </span>

          <div className="banner-body">
            <p className="banner-title">{title}</p>
            {children ? <div className="banner-text">{children}</div> : null}
          </div>

          {actions ? <div className="banner-actions">{actions}</div> : null}

          {dismissible ? (
            <button
              type="button"
              className="banner-dismiss"
              onClick={dismiss}
              aria-label={`Dismiss ${TONE_LABEL[tone].toLowerCase()}`}
            >
              <Icon name="close" size={15} />
            </button>
          ) : null}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
