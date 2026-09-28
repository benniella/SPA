"use client";

import { Reveal } from "@/components/motion/primitives";

export interface PageHeaderProps {
  /** Anchored by the section's 'aria-labelledby'. */
  readonly id: string;
  readonly eyebrow: string;
  readonly heading: string;
  readonly lede?: string;
}

export function PageHeader({ id, eyebrow, heading, lede }: PageHeaderProps) {
  return (
    <header className="page-header">
      <Reveal from="bottom">
        <p className="eyebrow text-accent">{eyebrow}</p>
        <h1 id={id} className="heading-page page-header-heading">
          {heading}
        </h1>
        {lede ? <p className="lede page-header-lede">{lede}</p> : null}
      </Reveal>
    </header>
  );
}
