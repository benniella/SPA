import { StaggerGroup, StaggerItem } from "@/components/motion/primitives";
import { Icon } from "@/components/ui/icon";
import { CAPABILITIES } from "@/data/marketing";

export function CapabilityStrip() {
  return (
    <aside className="capability-strip" aria-label="Product capabilities">
      <div className="container-page">
        <StaggerGroup as="ul" className="capability-list">
          {CAPABILITIES.map((capability) => (
            <StaggerItem key={capability.id} as="li" className="capability-item">
              <span className="capability-mark" aria-hidden="true" />
              <Icon name={capability.icon} size={14} />
              {capability.label}
            </StaggerItem>
          ))}
        </StaggerGroup>
      </div>
    </aside>
  );
}
