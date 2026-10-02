"use client";

import { Badge } from "@/components/ui/badge";

export interface StatusBadgeListProps {
  readonly items: readonly string[];
  readonly emptyLabel: string;
  readonly tone?: "neutral" | "accent" | "info";
}

/* Role names and privilege identifiers are different vocabularies: a role is a
   job such as 'support_admin' and a privilege is a capability such as
   'users.manage'. They are rendered from the backend's own strings so neither is
   inferred from the other. */
export function StatusBadgeList({ items, emptyLabel, tone = "neutral" }: StatusBadgeListProps) {
  if (items.length === 0) {
    return <p className="text-caption">{emptyLabel}</p>;
  }

  return (
    <ul className="row-center" aria-label={emptyLabel}>
      {items.map((item) => (
        <li key={item}>
          <Badge tone={tone}>{item}</Badge>
        </li>
      ))}
    </ul>
  );
}

export function RoleList({ items }: { items: readonly string[] }) {
  return <StatusBadgeList items={items} emptyLabel="No roles" tone="accent" />;
}

export function PrivilegeList({ items }: { items: readonly string[] }) {
  return <StatusBadgeList items={items} emptyLabel="No privileges" tone="info" />;
}
