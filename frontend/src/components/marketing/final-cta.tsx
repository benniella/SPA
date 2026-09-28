import { Reveal } from "@/components/motion/primitives";
import { ButtonLink } from "@/components/ui/button";
import { Container } from "@/components/ui/section";
import { FINAL_CTA } from "@/data/marketing";

export function FinalCta() {
  return (
    <section id="start" aria-labelledby="final-cta-headline" className="final-cta">
      <Container>
        <div className="final-cta-inner">
          <Reveal from="bottom" className="final-cta-copy">
            <div className="stack stack-5">
              <h2 id="final-cta-headline" className="heading-display final-cta-headline">
                {FINAL_CTA.headlineLines.map((line) => (
                  <span key={line} style={{ display: "block" }}>
                    {line}
                  </span>
                ))}
              </h2>
              <p className="lede">{FINAL_CTA.body}</p>
            </div>
          </Reveal>

          <Reveal from="none" delay={0.12}>
            {/* Style #01 — the SPA primary action, and the only action here. */}
            <ButtonLink
              href="/sign-in"
              variant="primary"
              size="lg"
              className="spa-button--hero"
            >
              {FINAL_CTA.cta.label}
            </ButtonLink>
          </Reveal>
        </div>
      </Container>
    </section>
  );
}
