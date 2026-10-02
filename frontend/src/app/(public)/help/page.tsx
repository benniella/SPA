import type { Metadata } from "next";
import Link from "next/link";

import { HelpChatbot } from "@/components/help/chatbot";
import { PageHeader } from "@/components/marketing/page-header";
import { Reveal } from "@/components/motion/primitives";
import { Container } from "@/components/ui/section";
import { HELP_TOPICS } from "@/data/help";

export const metadata: Metadata = {
  title: "Help center",
  description: "Answers to the questions that come up while signing in, verifying an account and using a workspace.",
  alternates: { canonical: "/help" },
  openGraph: {
    url: "/help",
    title: "Help center · SPA",
    description: "Sign-in, verification and workspace answers.",
  },
};

export default function HelpPage() {
  return (
    <Container width="narrow">
      <PageHeader
        id="help-headline"
        eyebrow="Help center"
        heading="How can we help?"
        lede="The answers below cover signing in, verifying an account and working inside a workspace. Ask the assistant for anything not listed."
      />

      <div className="help-topics">
        {HELP_TOPICS.map((topic, index) => (
          <Reveal key={topic.id} from="bottom" delay={index * 0.05}>
            <section id={topic.id} aria-labelledby={`${topic.id}-heading`} className="help-topic">
              <h2 id={`${topic.id}-heading`} className="heading-card">
                {topic.label}
              </h2>
              <p className="text-caption help-topic__intro">{topic.description}</p>

              <div className="help-articles">
                {topic.articles.map((article) => (
                  <details key={article.id} className="help-article">
                    <summary className="help-article__question">{article.question}</summary>
                    <p className="help-article__answer">{article.answer}</p>
                  </details>
                ))}
              </div>
            </section>
          </Reveal>
        ))}
      </div>

      <p className="text-caption help-note">
        Still stuck?{" "}
        <Link className="app-row-link" href="/contact">
          Contact the team
        </Link>
        .
      </p>

      <HelpChatbot />
    </Container>
  );
}
