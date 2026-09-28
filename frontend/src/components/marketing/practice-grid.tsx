"use client";

import { Reveal, StaggerGroup, StaggerItem } from "@/components/motion/primitives";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import type { StatusItem } from "@/data/public-pages";

export function PracticeGrid({ items }: { items: readonly StatusItem[] }) {
  return (
    <StaggerGroup as="ul" className="practice-grid">
      {items.map((item) => (
        <StaggerItem key={item.id} as="li">
          <div className="practice-card" data-status={item.status}>
            <div className="practice-card-head">
              <span className="practice-card-icon" aria-hidden="true">
                <Icon name={item.icon} size={16} />
              </span>
              <Badge tone={item.status === "current" ? "success" : "neutral"}>
                {item.status === "current" ? "In place" : "Planned"}
              </Badge>
            </div>
            <h3 className="heading-card">{item.label}</h3>
            <p className="text-caption">{item.description}</p>
          </div>
        </StaggerItem>
      ))}
    </StaggerGroup>
  );
}

export function PracticeSection({
  id,
  heading,
  children,
}: {
  id: string;
  heading: string;
  children: React.ReactNode;
}) {
  return (
    <Reveal from="bottom">
      <section id={id} aria-labelledby={`${id}-heading`} className="practice-section">
        <h2 id={`${id}-heading`} className="heading-subsection">
          {heading}
        </h2>
        {children}
      </section>
    </Reveal>
  );
}
