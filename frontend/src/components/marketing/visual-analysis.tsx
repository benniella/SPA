import { PitchVisualization } from "@/components/marketing/pitch-visualization";
import { Reveal } from "@/components/motion/primitives";
import { ButtonLink } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Section, SectionIntro } from "@/components/ui/section";
import { ANALYSIS_VIEWS, ILLUSTRATIVE_NOTE } from "@/data/marketing";

export function VisualAnalysis() {
  return (
    <Section id="visual-analysis" labelledBy="visual-headline" divider>
      <div className="stack stack-8">
        <Reveal>
          <SectionIntro
            id="visual-headline"
            eyebrow="Visual analysis"
            heading="See performance in motion"
            lede="Movement, density, shape and events are four views of the same tracked positions. Switching between them does not reload anything — they are different renderings of one coordinate space, not four screenshots."
          />
        </Reveal>

        <Reveal delay={0.08}>
          <PitchVisualization />
        </Reveal>

        <Reveal delay={0.12}>
          <div className="stack stack-5">
            <ul className="analysis-views">
              {ANALYSIS_VIEWS.map((view) => (
                <li key={view.id} className="analysis-view">
                  <span className="text-label text-accent">{view.label}</span>
                  <span className="text-caption">{view.description}</span>
                </li>
              ))}
            </ul>

            <p className="text-caption">
              {ILLUSTRATIVE_NOTE} Positions are drawn in metres on a 105 × 68 m pitch — the same
              coordinate convention the tracking and heatmap records use.
            </p>

            <div className="row-wrap">
              {/* Style #10 — premium secondary. */}
              <ButtonLink href="#insights" variant="technical">
                View All Reports
              </ButtonLink>

              {/* Style #05 — the everyday technical control. */}
              <ButtonLink
                href="#platform"
                variant="technical"
                icon={<Icon name="analytics" size={14} />}
              >
                Explore Sports
              </ButtonLink>
            </div>
          </div>
        </Reveal>
      </div>
    </Section>
  );
}
