"use client";

import { AnimatePresence, MotionConfig, motion, useInView, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

export const MOTION = {
  duration: {
    fast: 0.14,
    base: 0.22,
    slow: 0.42,
    reveal: 0.62,
  },
  easeOut: [0.16, 1, 0.3, 1] as const,
  easeStandard: [0.2, 0, 0, 1] as const,
  stagger: 0.06,
} as const;

export function MotionScope({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

export interface RevealProps {
  readonly children: ReactNode;
  readonly from?: "bottom" | "right" | "left" | "none";
  readonly delay?: number;
  readonly className?: string;
  readonly as?: "div" | "li" | "section" | "header" | "figure";
}

const OFFSET: Record<NonNullable<RevealProps["from"]>, { x: number; y: number }> = {
  bottom: { x: 0, y: 16 },
  right: { x: 20, y: 0 },
  left: { x: -20, y: 0 },
  none: { x: 0, y: 0 },
};

export function Reveal({
  children,
  from = "bottom",
  delay = 0,
  className,
  as = "div",
}: RevealProps) {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.25 });
  const reduced = useReducedMotion();

  const offset = OFFSET[from];

  if (reduced) {
    const Static = as;
    return <Static className={className}>{children}</Static>;
  }

  const animate = inView ? { opacity: 1, x: 0, y: 0 } : undefined;
  const transition = { duration: MOTION.duration.reveal, ease: MOTION.easeOut, delay };
  const initial = { opacity: 0, ...offset };

  /* Elements written out rather than indexed from 'motion[as]': that union has no
     call signature TypeScript can resolve. */
  if (as === "li") {
    return (
      <motion.li
        ref={ref as React.RefObject<HTMLLIElement>}
        className={className}
        initial={initial}
        animate={animate}
        transition={transition}
      >
        {children}
      </motion.li>
    );
  }

  if (as === "section") {
    return (
      <motion.section
        ref={ref as React.RefObject<HTMLElement>}
        className={className}
        initial={initial}
        animate={animate}
        transition={transition}
      >
        {children}
      </motion.section>
    );
  }

  if (as === "header") {
    return (
      <motion.header
        ref={ref as React.RefObject<HTMLElement>}
        className={className}
        initial={initial}
        animate={animate}
        transition={transition}
      >
        {children}
      </motion.header>
    );
  }

  if (as === "figure") {
    return (
      <motion.figure
        ref={ref as React.RefObject<HTMLElement>}
        className={className}
        initial={initial}
        animate={animate}
        transition={transition}
      >
        {children}
      </motion.figure>
    );
  }

  return (
    <motion.div
      ref={ref as React.RefObject<HTMLDivElement>}
      className={className}
      initial={initial}
      animate={animate}
      transition={transition}
    >
      {children}
    </motion.div>
  );
}

/* Stagger group */

export interface StaggerGroupProps {
  readonly children: ReactNode;
  readonly delay?: number;
  readonly className?: string;
  readonly as?: "div" | "ul" | "ol";
}

export function StaggerGroup({ children, delay = 0, className, as = "div" }: StaggerGroupProps) {
  const ref = useRef<HTMLDivElement>(null);
  const ulRef = useRef<HTMLUListElement>(null);
  const inView = useInView(as === "ul" ? ulRef : ref, { once: true, amount: 0.2 });
  const reduced = useReducedMotion();

  if (reduced) {
    const Static = as;
    return <Static className={className}>{children}</Static>;
  }

  /* Two branches, each with its own typed ref: indexing 'motion[as]' gives a union
     with no call signature, and 'ol' is unused (numbered lists render as 'ul' with
     the index as text, because the numbers are part of the design). */
  if (as === "ul") {
    return (
      <motion.ul
        ref={ulRef}
        className={className}
        initial="hidden"
        animate={inView ? "visible" : "hidden"}
        variants={GROUP_VARIANTS(delay)}
      >
        {children}
      </motion.ul>
    );
  }

  return (
    <motion.div
      ref={ref}
      className={className}
      initial="hidden"
      animate={inView ? "visible" : "hidden"}
      variants={GROUP_VARIANTS(delay)}
    >
      {children}
    </motion.div>
  );
}

function GROUP_VARIANTS(delay: number) {
  return {
    hidden: {},
    visible: { transition: { staggerChildren: MOTION.stagger, delayChildren: delay } },
  };
}

export function StaggerItem({
  children,
  className,
  as = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "li";
}) {
  const reduced = useReducedMotion();

  if (reduced) {
    const Static = as;
    return <Static className={className}>{children}</Static>;
  }

  const Component = as === "div" ? motion.div : motion.li;

  return (
    <Component
      className={className}
      variants={{
        hidden: { opacity: 0, y: 12 },
        visible: {
          opacity: 1,
          y: 0,
          transition: { duration: MOTION.duration.slow, ease: MOTION.easeOut },
        },
      }}
    >
      {children}
    </Component>
  );
}

/* Animated metric value */

export interface AnimatedMetricValueProps {
  readonly value: string;
  readonly className?: string;
}

export function AnimatedMetricValue({ value, className }: AnimatedMetricValueProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.6 });
  const reduced = useReducedMotion();

  const target = Number.parseFloat(value);
  const animatable = Number.isFinite(target) && /^[0-9]*\.?[0-9]+$/.test(value.trim());
  const [display, setDisplay] = useState(animatable && !reduced ? "0" : value);

  useEffect(() => {
    if (!animatable || reduced || !inView) return;

    const decimals = value.includes(".") ? (value.split(".")[1]?.length ?? 0) : 0;
    const durationMs = 900;
    const start = performance.now();
    let frame = 0;

    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / durationMs);
      const eased = 1 - (1 - progress) ** 3;
      setDisplay(progress === 1 ? value : (target * eased).toFixed(decimals));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [animatable, reduced, inView, target, value]);

  return (
    <span ref={ref} className={className} data-numeric>
      {animatable && !reduced ? display : value}
    </span>
  );
}

/* Presence */

/** Re-exported so consumers do not import Framer Motion directly. */
export { AnimatePresence, motion };

export function usePrefersReducedMotion(): boolean {
  return useReducedMotion() ?? false;
}
