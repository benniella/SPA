import { Icon } from "@/components/ui/icon";
import type { IconName } from "@/data/marketing";
import { ILLUSTRATIVE_NOTE, ILLUSTRATIVE_NOTE_SHORT } from "@/data/marketing";

export type BadgeTone = "neutral" | "accent" | "info" | "success" | "warning" | "danger";

interface BadgeProps {
  children: React.ReactNode;
  tone?: BadgeTone;
  icon?: IconName;
  className?: string;
}

export function Badge({ children, tone = "neutral", icon, className }: BadgeProps) {
  return (
    <span className={["badge", `badge-${tone}`, className].filter(Boolean).join(" ")}>
      {icon ? <Icon name={icon} size={11} /> : null}
      {children}
    </span>
  );
}

interface IllustrativeTagProps {
  variant?: "full" | "short";
  className?: string;
}

export function IllustrativeTag({ variant = "short", className }: IllustrativeTagProps) {
  const label = variant === "full" ? ILLUSTRATIVE_NOTE : ILLUSTRATIVE_NOTE_SHORT;

  return (
    <span
      className={["badge badge-neutral", className].filter(Boolean).join(" ")}
      title={ILLUSTRATIVE_NOTE}
    >
      <span aria-hidden="true">{label}</span>
      <span className="visually-hidden">{ILLUSTRATIVE_NOTE}</span>
    </span>
  );
}
