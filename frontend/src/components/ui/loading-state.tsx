"use client";

import { motion, useReducedMotion } from "motion/react";

import { MOTION } from "@/components/motion/primitives";

export interface LoadingStateProps {
  readonly label: string;
  readonly rows?: number;
  readonly className?: string;
}

export function LoadingState({ label, rows = 4, className }: LoadingStateProps) {
  const reduced = useReducedMotion();

  return (
    <div
      className={["skeleton", className].filter(Boolean).join(" ")}
      role="status"
      aria-live="polite"
    >
      <span className="text-label">{label}</span>
      <motion.div
        className="skeleton-rows"
        aria-hidden="true"
        initial={reduced ? { opacity: 1 } : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: MOTION.duration.base, ease: MOTION.easeOut }}
      >
        {Array.from({ length: rows }, (_, index) => (
          <div
            key={index}
            className="skeleton-row"
            data-width={index === 0 ? "medium" : index % 3 === 2 ? "short" : "full"}
          />
        ))}
      </motion.div>
    </div>
  );
}

export function LoadingDetail({ label }: { label: string }) {
  return <LoadingState label={label} rows={5} />;
}
