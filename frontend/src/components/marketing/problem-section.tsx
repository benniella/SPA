import { VideoPerformanceVisualization } from "@/components/marketing/pipeline-visualization";
import { Reveal } from "@/components/motion/primitives";
import { Section, SectionIntro } from "@/components/ui/section";
import { PROBLEM } from "@/data/marketing";

export function ProblemSection() {
  return (
    <Section id="platform" labelledBy="problem-headline">
      <div className="stack stack-8">
        <Reveal>
          <SectionIntro
            id="problem-headline"
            eyebrow="The problem"
            heading={PROBLEM.headline}
            lede={PROBLEM.body}
          />
        </Reveal>

        {/* An ordered list because each stage is a consequence of the one before. */}
        <Reveal delay={0.1}>
          <ol className="problem-stages">
            {PROBLEM.stages.map((stage) => (
              <li key={stage.id} className="problem-stage">
                <span className="heading-card">{stage.label}</span>
                <span className="text-body">{stage.detail}</span>
              </li>
            ))}
          </ol>
        </Reveal>

        <Reveal delay={0.15}>
          <VideoPerformanceVisualization />
        </Reveal>
      </div>
    </Section>
  );
}
