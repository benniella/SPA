import { HeroAnalysisVisual } from "@/components/marketing/hero-analysis";
import { Reveal } from "@/components/motion/primitives";
import { ButtonLink } from "@/components/ui/button";
import { Container } from "@/components/ui/section";
import { HERO } from "@/data/marketing";

export function Hero() {
  return (
    <section id="top" aria-labelledby="hero-headline" className="hero">
      <Container>
        <div className="hero-grid">
          <div className="stack stack-6">
            <Reveal from="none" className="stack stack-4">
              <p className="eyebrow">{HERO.eyebrow}</p>

              <h1 id="hero-headline" className="heading-display hero-headline">
                {HERO.headlineLines.map((line) => (
                  <span key={line} style={{ display: "block" }}>
                    {line}
                  </span>
                ))}
              </h1>

              <p className="lede">{HERO.supporting}</p>
            </Reveal>

            <Reveal from="none" delay={0.1}>
              <div className="stack stack-3">
                <p className="text-body">{HERO.explanation.lineOne}</p>
                <p className="text-body">{HERO.explanation.lineTwo}</p>
              </div>
            </Reveal>

            <Reveal from="none" delay={0.18}>
              <div className="hero-actions">
                <ButtonLink
                  href="/sign-in"
                  variant="primary"
                  size="lg"
                  className="spa-button--hero"
                >
                  {HERO.primaryCta.label}
                </ButtonLink>

                <ButtonLink
                  href={HERO.secondaryCta.href}
                  variant="technical"
                  size="lg"
                  className="spa-button--hero"
                >
                  {HERO.secondaryCta.label}
                </ButtonLink>
              </div>
            </Reveal>
          </div>

          <Reveal from="right" delay={0.1} className="hero-visual">
            <HeroAnalysisVisual />
          </Reveal>
        </div>
      </Container>
    </section>
  );
}
