import { Reveal } from "@/components/motion/primitives";
import { Container } from "@/components/ui/section";
import { Banner } from "@/components/ui/banner";
import { PageHeader } from "@/components/marketing/page-header";
import type { ContentSection } from "@/data/public-pages";

export interface DocumentPageProps {
  /** Anchor id for the '<h1>'. */
  readonly id: string;
  readonly eyebrow: string;
  readonly heading: string;
  readonly lede?: string;
  readonly notice?: { readonly title: string; readonly body: string };
  readonly effectiveDate?: string;
  readonly sections: readonly ContentSection[];
  /** Used by compliance and security for their trailing cards. */
  readonly children?: React.ReactNode;
}

export function DocumentPage({
  id,
  eyebrow,
  heading,
  lede,
  notice,
  effectiveDate,
  sections,
  children,
}: DocumentPageProps) {
  return (
    <Container width="narrow">
      <PageHeader id={id} eyebrow={eyebrow} heading={heading} lede={lede} />

      {effectiveDate ? <p className="text-micro page-meta">Status: {effectiveDate}</p> : null}

      {notice ? (
        <div className="page-notice">
          <Banner tone="warning" title={notice.title}>
            <p>{notice.body}</p>
          </Banner>
        </div>
      ) : null}

      {children}

      <div className="document-body">
        {sections.map((section, index) => (
          <Reveal key={section.id} from="bottom" delay={Math.min(index * 0.03, 0.12)}>
            <section
              id={section.id}
              aria-labelledby={`${section.id}-heading`}
              className="document-section"
            >
              <h2 id={`${section.id}-heading`} className="heading-subsection document-heading">
                {section.heading}
              </h2>

              {section.paragraphs.map((paragraph) => (
                <p key={paragraph} className="text-body document-paragraph">
                  {paragraph}
                </p>
              ))}

              {section.items ? (
                <ul className="document-list">
                  {section.items.map((item) => (
                    <li key={item} className="document-list-item">
                      {item}
                    </li>
                  ))}
                </ul>
              ) : null}

              {section.placeholder ? (
                <p className="document-placeholder">
                  <span className="text-micro">Open item</span>
                  This section describes an unresolved decision rather than a settled term.
                </p>
              ) : null}
            </section>
          </Reveal>
        ))}
      </div>
    </Container>
  );
}
