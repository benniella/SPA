import Link from "next/link";

import { BRAND } from "@/data/marketing";

export type BrandVariant = "full" | "compact";

interface BrandMarkProps {
  readonly variant?: BrandVariant;
  readonly asLink?: boolean;
  readonly className?: string;
}

export function BrandMark({ variant = "full", asLink = false, className }: BrandMarkProps) {
  const classes = ["brand-mark", className].filter(Boolean).join(" ");

  const content = (
    <>
      <span className="brand-mark-chevron" aria-hidden="true" />
      <span className="brand-mark-word">{BRAND.name}</span>
      {variant === "full" ? <span className="brand-mark-sub">{BRAND.expansion}</span> : null}
    </>
  );

  if (asLink) {
    return (
      <Link
        href="/#top"
        className={classes}
        aria-label={`${BRAND.name} — ${BRAND.expansion}, home`}
      >
        {content}
      </Link>
    );
  }

  return <span className={classes}>{content}</span>;
}
