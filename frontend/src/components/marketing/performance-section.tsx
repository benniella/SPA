import { AthletePerformancePanel } from "@/components/marketing/athlete-panel";
import { Reveal, StaggerGroup, StaggerItem } from "@/components/motion/primitives";
import { Section, SectionIntro } from "@/components/ui/section";
import { PERFORMANCE_METRICS } from "@/data/marketing";

export function PerformanceSection() {
  return (
    <Section id="performance" labelledBy="performance-headline">
      <div className="stack stack-8">
        <Reveal>
          <SectionIntro
            id="performance-headline"
            eyebrow="Performance"
            heading="From movement to meaning"
            lede="A trajectory is not a number a coach can use. These are the metric families that turn positions over time into something comparable — across players, across units, across matches."
          />
        </Reveal>

        <StaggerGroup as="div" className="metric-grid">
          {PERFORMANCE_METRICS.map((metric, index) => (
            <StaggerItem key={metric.id} as="div">
              {/* 'magnitude' is omitted: there is no denominator here, and a bar
                  with nothing behind it is decoration dressed as data. */}
              <div className="metric">
                <p className="text-label">{metric.label}</p>
                <p className="metric-value">
                  <span className="text-faint">—</span>
                  {metric.unit ? <span className="metric-unit">{metric.unit}</span> : null}
                </p>
                <p className="text-caption" style={{ marginTop: "var(--space-3)" }}>
                  {metric.definition}
                </p>
                <span className="visually-hidden">
                  {`Metric family ${index + 1} of ${PERFORMANCE_METRICS.length}. Values are produced by analysis runs and are not shown here.`}
                </span>
              </div>
            </StaggerItem>
          ))}
        </StaggerGroup>

        <Reveal from="bottom" delay={0.1}>
          <AthletePerformancePanel />
        </Reveal>
      </div>
    </Section>
  );
}
