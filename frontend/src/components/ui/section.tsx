import type { ElementType, ReactNode } from "react";

/* Container */

export type ContainerWidth = "page" | "narrow" | "full";

export interface ContainerProps {
  readonly width?: ContainerWidth;
  readonly className?: string;
  readonly children: ReactNode;
}

const CONTAINER_CLASS: Record<ContainerWidth, string> = {
  page: "container-page",
  narrow: "container-narrow",
  full: "w-full",
};

export function Container({ width = "page", className, children }: ContainerProps) {
  return (
    <div className={[CONTAINER_CLASS[width], className].filter(Boolean).join(" ")}>{children}</div>
  );
}

/* Section */

export interface SectionProps {
  /** Anchor target, referenced by the navigation and the footer. */
  readonly id: string;
  /** The id of the heading element that names this section. */
  readonly labelledBy: string;
  readonly spacing?: "default" | "tight" | "none";
  readonly divider?: boolean;
  readonly width?: ContainerWidth;
  readonly className?: string;
  readonly children: ReactNode;
}

export function Section({
  id,
  labelledBy,
  spacing = "default",
  divider = false,
  width = "page",
  className,
  children,
}: SectionProps) {
  const classes = [
    spacing === "default" ? "section" : null,
    spacing === "tight" ? "section-tight" : null,
    divider ? "section-divider" : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section id={id} aria-labelledby={labelledBy} className={classes}>
      <Container width={width}>{children}</Container>
    </section>
  );
}

/* Heading */

export type HeadingLevel = 1 | 2 | 3 | 4;

export interface HeadingProps {
  readonly id?: string;
  readonly level?: HeadingLevel;
  readonly size?: "display" | "page" | "section" | "subsection" | "card";
  /** Section labels and the hero are uppercase. Body prose never is. */
  readonly uppercase?: boolean;
  readonly className?: string;
  readonly children: ReactNode;
}

const HEADING_SIZE_CLASS = {
  display: "heading-display",
  page: "heading-page",
  section: "heading-section",
  subsection: "heading-subsection",
  card: "heading-card",
} as const;

export function Heading({
  id,
  level = 2,
  size = "section",
  uppercase = false,
  className,
  children,
}: HeadingProps) {
  const Tag: ElementType = `h${level}` as ElementType;

  return (
    <Tag
      id={id}
      className={[HEADING_SIZE_CLASS[size], className].filter(Boolean).join(" ")}
      {...(uppercase ? { "data-case": "uppercase" } : {})}
    >
      {children}
    </Tag>
  );
}

/** The eyebrow + heading + lede stack that opens most sections. */
export interface SectionIntroProps {
  readonly id: string;
  readonly eyebrow?: string;
  readonly heading: ReactNode;
  readonly lede?: ReactNode;
  readonly level?: HeadingLevel;
  readonly uppercase?: boolean;
}

export function SectionIntro({
  id,
  eyebrow,
  heading,
  lede,
  level = 2,
  uppercase = false,
}: SectionIntroProps) {
  return (
    <header className="stack stack-4">
      {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
      <Heading id={id} level={level} size="section" uppercase={uppercase}>
        {heading}
      </Heading>
      {lede ? <p className="lede">{lede}</p> : null}
    </header>
  );
}
