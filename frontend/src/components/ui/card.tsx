import type { ReactNode } from "react";

/* Card */

export interface CardProps {
  readonly variant?: "plain" | "flush";
  readonly tone?: "surface" | "placeholder";
  readonly className?: string;
  readonly children: ReactNode;
}

export function Card({ variant = "plain", tone = "surface", className, children }: CardProps) {
  const classes = [
    tone === "placeholder" ? "card-placeholder" : "card",
    variant === "flush" ? "card-flush" : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return <div className={classes}>{children}</div>;
}

/* Metric */

export interface MetricProps {
  readonly label: string;
  readonly value: string | number;
  readonly unit?: string;
  readonly definition?: string;
  readonly magnitude?: number;
  readonly emphasis?: boolean;
  readonly className?: string;
}

export function Metric({
  label,
  value,
  unit,
  definition,
  magnitude,
  emphasis = false,
  className,
}: MetricProps) {
  const clamped = typeof magnitude === "number" ? Math.min(1, Math.max(0, magnitude)) : undefined;

  return (
    <div className={["metric", className].filter(Boolean).join(" ")}>
      <p className="text-label">{label}</p>
      <p className="metric-value" data-numeric>
        <span className={emphasis ? "text-accent" : undefined}>{value}</span>
        {unit ? <span className="metric-unit">{unit}</span> : null}
      </p>
      {definition ? (
        <p className="text-caption" style={{ marginTop: "var(--space-2)" }}>
          {definition}
        </p>
      ) : null}
      {clamped !== undefined ? (
        <div
          className="metric-bar"
          style={{ marginTop: "var(--space-3)" }}
          role="presentation"
          aria-hidden="true"
        >
          {/* The bar repeats a value the text already states, so it is marked
              decorative rather than given a redundant ARIA role. */}
          <div className="metric-bar-fill" style={{ width: `${clamped * 100}%` }} />
        </div>
      ) : null}
    </div>
  );
}

/* Divider */

export interface DividerProps {
  readonly label?: string;
  readonly className?: string;
}

export function Divider({ label, className }: DividerProps) {
  if (label) {
    return <p className={["divider-label", className].filter(Boolean).join(" ")}>{label}</p>;
  }

  return <hr className={["divider", className].filter(Boolean).join(" ")} />;
}

/* Ruled list */

export interface RuledItemProps {
  readonly index?: string;
  readonly children: ReactNode;
  readonly trailing?: ReactNode;
}

export function RuledItem({ index, children, trailing }: RuledItemProps) {
  return (
    <li className="ruled-item">
      <span className="row-center">
        {index ? <span className="ruled-item-index">{index}</span> : null}
        <span>{children}</span>
      </span>
      {trailing ? <span className="text-caption ruled-item-trailing">{trailing}</span> : null}
    </li>
  );
}

export function RuledList({ children, className }: { children: ReactNode; className?: string }) {
  return <ul className={["ruled-list", className].filter(Boolean).join(" ")}>{children}</ul>;
}
