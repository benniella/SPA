import { EnginePipelineVisualization } from "@/components/marketing/pipeline-visualization";
import { Reveal, StaggerGroup, StaggerItem } from "@/components/motion/primitives";
import { ButtonLink } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Section, SectionIntro } from "@/components/ui/section";
import { PROCESS_STEPS } from "@/data/marketing";

export function AiEngine() {
  return (
    <Section id="ai-engine" labelledBy="engine-headline" divider>
      <div className="stack stack-8">
        <Reveal>
          <SectionIntro
            id="engine-headline"
            eyebrow="Process"
            heading="How SPA works"
            lede="Five stages take a recording to a set of numbers you can compare. Each stage produces something the next one can use, which is what makes a metric traceable back to the frame it came from."
          />
        </Reveal>

        <StaggerGroup as="ul" className="process-list">
          {PROCESS_STEPS.map((step) => (
            <StaggerItem key={step.id} as="li" className="process-step">
              <div className="stack stack-3">
                <span className="text-accent" aria-hidden="true">
                  <Icon name={step.icon} size={18} />
                </span>
                <h3 className="heading-card">{step.title}</h3>
                <p className="text-caption">{step.description}</p>
              </div>
            </StaggerItem>
          ))}
        </StaggerGroup>

        <Reveal delay={0.12}>
          <div className="stack stack-5">
            <div className="stack stack-2">
              <h3 className="heading-subsection">Inside the engine</h3>
              <p className="text-body">
                Detection, tracking and pose read the footage. Everything after them is computation
                over the tracking data those stages produce — which is why the same movement metrics
                work across sports.
              </p>
            </div>

            <EnginePipelineVisualization />
          </div>
        </Reveal>

        <Reveal delay={0.16}>
          <div className="row-wrap">
            <ButtonLink href="/sign-in" variant="ai" size="lg">
              Run AI Analysis
            </ButtonLink>
            <ButtonLink href="/sign-in" variant="technical" size="lg">
              View Documentation
            </ButtonLink>
          </div>
        </Reveal>
      </div>
    </Section>
  );
}
