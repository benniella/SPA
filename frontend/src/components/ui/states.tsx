import type { ReactNode } from "react";

import { Icon } from "@/components/ui/icon";
import type { IconName } from "@/data/marketing";

export type StateTone = "empty" | "placeholder" | "error";

export interface StateBlockProps {
  readonly tone?: StateTone;
  readonly icon?: IconName;
  readonly title: string;
  readonly description: ReactNode;
  /** The next step. Omitted only when there genuinely is not one. */
  readonly actions?: ReactNode;
  readonly className?: string;
}

/** The error state keeps an icon because it has to be recognisable at a glance. The
 * empty and placeholder states carry their meaning in the title and the border style,
 * so an icon on every card is decoration. */
const DEFAULT_ICON: Partial<Record<StateTone, IconName>> = {
  error: "close",
};

const TONE_LABEL: Record<StateTone, string> = {
  empty: "Nothing here yet",
  placeholder: "Not available yet",
  error: "Something went wrong",
};

export function StateBlock({
  tone = "empty",
  icon,
  title,
  description,
  actions,
  className,
}: StateBlockProps) {
  const toneIcon = icon ?? DEFAULT_ICON[tone];

  return (
    <section
      className={["state-block", className].filter(Boolean).join(" ")}
      data-tone={tone}
      aria-label={TONE_LABEL[tone]}
    >
      {toneIcon ? (
        <span className="state-icon" aria-hidden="true">
          <Icon name={toneIcon} size={20} />
        </span>
      ) : null}
      <h2 className="state-title">{title}</h2>
      <div className="state-text">{description}</div>
      {actions ? <div className="state-actions">{actions}</div> : null}
    </section>
  );
}

/* Empty */

export interface EmptyStateProps {
  readonly title: string;
  readonly description: ReactNode;
  readonly actions?: ReactNode;
  readonly icon?: IconName;
}

/** Nothing exists yet, and the reader can create it. */
export function EmptyState({ title, description, actions, icon }: EmptyStateProps) {
  return (
    <StateBlock
      tone="empty"
      title={title}
      description={description}
      actions={actions}
      icon={icon}
    />
  );
}

/* Planned */

export interface PlannedStateProps {
  readonly title: string;
  readonly description: ReactNode;
  /** What would unblock it. Shown as a note rather than as a button, because
   * there is nothing to click. */
  readonly note?: string;
}

/** A capability that is designed, named and routed but not implemented. */
export function PlannedState({ title, description, note }: PlannedStateProps) {
  return (
    <StateBlock
      tone="placeholder"
      title={title}
      description={
        <>
          {description}
          {note ? (
            <p className="text-caption" style={{ marginTop: "var(--space-3)" }}>
              {note}
            </p>
          ) : null}
        </>
      }
    />
  );
}
