import { Reveal, StaggerGroup, StaggerItem } from "@/components/motion/primitives";
import { Badge, IllustrativeTag } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { Metric } from "@/components/ui/card";
import { Section, SectionIntro } from "@/components/ui/section";
import { INSIGHTS, ILLUSTRATIVE_NOTE } from "@/data/marketing";

const REPORT_ROWS: readonly {
  readonly id: string;
  readonly subject: string;
  readonly scope: string;
}[] = [
  { id: "movement", subject: "Distance by period", scope: "player · team" },
  { id: "intensity", subject: "High-intensity efforts", scope: "player" },
  { id: "shape", subject: "Team shape over time", scope: "team" },
  { id: "workload", subject: "Workload distribution", scope: "squad" },
  { id: "events", subject: "Timed events and positions", scope: "match" },
];

export function InsightsSection() {
  return (
    <Section id="insights" labelledBy="insights-headline">
      <div className="stack stack-8">
        <Reveal>
          <SectionIntro
            id="insights-headline"
            eyebrow="Insights"
            heading={INSIGHTS.headline}
            lede={INSIGHTS.body}
          />
        </Reveal>

        {/* An ordered list, because the arrow is a claim about dependency. */}
        <Reveal delay={0.08}>
          <ol className="chain">
            {INSIGHTS.chain.map((stage, index) => (
              <li key={stage.id} className="chain-step">
                <span className="chain-step-label">{stage.label}</span>
                <span className="text-body">{stage.description}</span>
                {/* Vertical connector for the stacked mobile layout. Hidden
                    above 48rem, where the horizontal rule takes over. */}
                {index < INSIGHTS.chain.length - 1 ? (
                  <span className="chain-arrow" aria-hidden="true">
                    <Icon name="arrow-down" size={18} />
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
        </Reveal>

        <div className="insights-panel">
          <Reveal from="left" className="insights-report">
            <div className="viz-frame">
              <div className="viz-header">
                <span className="row-center">
                  <Icon name="analytics" size={14} />
                  <span className="text-label">Report structure</span>
                </span>
                <IllustrativeTag />
              </div>

              <ul className="report-rows">
                {REPORT_ROWS.map((row) => (
                  <li key={row.id} className="report-row">
                    <span className="report-row-subject">{row.subject}</span>
                    <Badge tone="neutral">{row.scope}</Badge>
                  </li>
                ))}
              </ul>

              <p className="text-caption" style={{ padding: "var(--space-4)" }}>
                The sections a generated report is built from. Figures appear once an analysis run
                has produced metrics — nothing here is a measured value.
              </p>
            </div>
          </Reveal>

          <Reveal from="right" delay={0.08} className="insights-families">
            <StaggerGroup as="div" className="insights-metric-grid">
              <StaggerItem as="div">
                <Metric label="Scope" value="Player" definition="Attributed to one athlete." />
              </StaggerItem>
              <StaggerItem as="div">
                <Metric
                  label="Scope"
                  value="Team"
                  definition="Aggregated across a unit or squad."
                />
              </StaggerItem>
              <StaggerItem as="div">
                <Metric
                  label="Scope"
                  value="Match"
                  definition="Compared across a fixture or season."
                />
              </StaggerItem>
            </StaggerGroup>

            <div className="insights-note">
              <p className="text-body">
                Every metric keeps the run that produced it and the definition version it was
                computed with, so a number from last season is still interpretable this season.
              </p>
              <p className="visually-hidden">{ILLUSTRATIVE_NOTE}</p>
            </div>
          </Reveal>
        </div>
      </div>
    </Section>
  );
}
