import { Reveal, StaggerGroup, StaggerItem } from "@/components/motion/primitives";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { RuledList, RuledItem } from "@/components/ui/card";
import { Section, SectionIntro } from "@/components/ui/section";
import { SPORTS, SPORTS_STATEMENT } from "@/data/marketing";

export function MultiSport() {
  return (
    <Section id="sports" labelledBy="sports-headline">
      <div className="sports-layout">
        <Reveal className="sports-intro">
          <div className="stack stack-5">
            <SectionIntro
              id="sports-headline"
              eyebrow="Multi-sport"
              heading={SPORTS_STATEMENT.headline}
              lede={SPORTS_STATEMENT.supporting}
            />
          </div>
        </Reveal>

        <StaggerGroup as="ul" className="sports-list">
          {SPORTS.map((sport) => (
            <StaggerItem key={sport.id} as="li">
              <div className="sport-item">
                <span className="sport-item-label">{sport.label}</span>
                <span className="sport-item-status">
                  {sport.status === "modelled" ? (
                    <Badge tone="accent">Modelled</Badge>
                  ) : (
                    <Badge tone="neutral">Planned</Badge>
                  )}
                </span>
              </div>
            </StaggerItem>
          ))}

          {/* "More" is not a sport, so it is not in 'SPORTS' — that array is
              iterated elsewhere and would be corrupted by it. */}
          <StaggerItem as="li">
            <div className="sport-item sport-item-more">
              <Icon name="arrow-right" size={16} />
              <span className="sport-item-label">More</span>
              <span className="sport-item-status text-caption">As pitch geometry is defined</span>
            </div>
          </StaggerItem>
        </StaggerGroup>
      </div>

      <div className="sports-coda">
        <RuledList>
          <RuledItem trailing="shared">Detection</RuledItem>
          <RuledItem trailing="shared">Tracking</RuledItem>
          <RuledItem trailing="per sport">Pitch geometry</RuledItem>
          <RuledItem trailing="per sport">Movement thresholds</RuledItem>
        </RuledList>
      </div>
    </Section>
  );
}
