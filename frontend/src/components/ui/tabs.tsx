"use client";

import { useId, useRef, useState } from "react";
import type { ReactNode } from "react";

import { Icon } from "@/components/ui/icon";
import type { IconName } from "@/data/marketing";

/* Icon button */

export interface IconButtonProps {
  readonly icon: IconName;
  readonly label: string;
  readonly onClick?: () => void;
  /** Renders 'aria-expanded', for a control that discloses a panel. */
  readonly expanded?: boolean;
  readonly controls?: string;
  readonly className?: string;
}

export function IconButton({
  icon,
  label,
  onClick,
  expanded,
  controls,
  className,
}: IconButtonProps) {
  return (
    <button
      type="button"
      className={["icon-button", className].filter(Boolean).join(" ")}
      onClick={onClick}
      aria-label={label}
      {...(expanded === undefined ? {} : { "aria-expanded": expanded })}
      {...(controls ? { "aria-controls": controls } : {})}
    >
      <Icon name={icon} size={18} />
    </button>
  );
}

/* Tabs */

export interface TabItem {
  readonly id: string;
  readonly label: string;
  readonly content: ReactNode;
}

export interface TabsProps {
  readonly items: readonly TabItem[];
  /** Names this tab set, so two groups on one page do not collide in the a11y tree. */
  readonly label: string;
  readonly defaultTabId?: string;
}

export function Tabs({ items, label, defaultTabId }: TabsProps) {
  const baseId = useId();
  const [selected, setSelected] = useState(defaultTabId ?? items[0]?.id ?? "");
  const listRef = useRef<HTMLDivElement>(null);

  const tabId = (id: string) => `${baseId}-tab-${id}`;
  const panelId = (id: string) => `${baseId}-panel-${id}`;

  function selectAndFocus(id: string) {
    setSelected(id);
    const node = listRef.current?.querySelector<HTMLButtonElement>(`#${CSS.escape(tabId(id))}`);
    node?.focus();
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const currentIndex = items.findIndex((item) => item.id === selected);
    if (currentIndex === -1) return;

    // Both orientations are supported because the list wraps.
    const forward = event.key === "ArrowRight" || event.key === "ArrowDown";
    const backward = event.key === "ArrowLeft" || event.key === "ArrowUp";

    if (forward || backward) {
      event.preventDefault();
      const delta = forward ? 1 : -1;
      const next = items[(currentIndex + delta + items.length) % items.length];
      if (next) selectAndFocus(next.id);
      return;
    }

    if (event.key === "Home") {
      event.preventDefault();
      const first = items[0];
      if (first) selectAndFocus(first.id);
    }

    if (event.key === "End") {
      event.preventDefault();
      const last = items[items.length - 1];
      if (last) selectAndFocus(last.id);
    }
  }

  const active = items.find((item) => item.id === selected) ?? items[0];

  return (
    <div>
      <div
        ref={listRef}
        className="tab-list"
        role="tablist"
        aria-label={label}
        onKeyDown={handleKeyDown}
      >
        {items.map((item) => {
          const isSelected = item.id === active?.id;
          return (
            <button
              key={item.id}
              id={tabId(item.id)}
              type="button"
              role="tab"
              className="tab"
              aria-selected={isSelected}
              aria-controls={panelId(item.id)}
              // Roving tabindex: one stop for the whole set, arrow keys inside.
              tabIndex={isSelected ? 0 : -1}
              onClick={() => setSelected(item.id)}
            >
              {item.label}
            </button>
          );
        })}
      </div>

      {active ? (
        <div
          id={panelId(active.id)}
          className="tab-panel"
          role="tabpanel"
          aria-labelledby={tabId(active.id)}
          tabIndex={0}
        >
          {active.content}
        </div>
      ) : null}
    </div>
  );
}
