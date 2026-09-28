import { Icon } from "@/components/ui/icon";
import { Reveal, StaggerGroup, StaggerItem } from "@/components/motion/primitives";
import { Section, SectionIntro } from "@/components/ui/section";
import { AUDIENCES } from "@/data/marketing";

export function AudienceSection() {
  return (
    <Section id="audience" labelledBy="audience-headline">
      <div className="stack stack-8">
        <Reveal>
          <SectionIntro
            id="audience-headline"
            eyebrow="Audience"
            heading="Who SPA is for"
            lede="Everyone in a performance department needs something different from the same footage. SPA is built around those questions rather than around a single dashboard."
          />
        </Reveal>

        <StaggerGroup as="ul" className="audience-list">
          {AUDIENCES.map((audience) => (
            <StaggerItem key={audience.id} as="li" className="audience-item">
              <h3 className="audience-item-label">{audience.label}</h3>
              <p className="audience-item-need">
                <span className="audience-item-arrow" aria-hidden="true">
                  <Icon name="arrow-right" size={12} />
                </span>
                {audience.need}
              </p>
            </StaggerItem>
          ))}
        </StaggerGroup>
      </div>
    </Section>
  );
}
