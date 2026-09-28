import type { Metadata } from "next";

import { PageHeader } from "@/components/marketing/page-header";
import { Reveal } from "@/components/motion/primitives";
import { Banner } from "@/components/ui/banner";
import { Icon } from "@/components/ui/icon";
import { Container } from "@/components/ui/section";
import { CONTACT, CONTACT_CHANNELS } from "@/data/public-pages";

export const metadata: Metadata = {
  title: "Contact",
  description: "How to reach SPA for general enquiries, security reports and API documentation.",
  alternates: { canonical: "/contact" },
  openGraph: {
    url: "/contact",
    title: "Contact · SPA",
    description: "How to reach SPA.",
  },
};

export default function ContactPage() {
  return (
    <Container width="narrow">
      <PageHeader
        id="contact-headline"
        eyebrow="Contact"
        heading="Get in touch"
        lede="General enquiries, security reports and developer documentation."
      />

      {CONTACT.isPlaceholder ? (
        <div className="page-notice">
          <Banner tone="warning" title="No monitored mailbox yet" dismissible={false}>
            <p>{CONTACT.note}</p>
          </Banner>
        </div>
      ) : null}

      <div className="contact-list">
        {CONTACT_CHANNELS.map((channel, index) => (
          <Reveal key={channel.id} from="bottom" delay={index * 0.05}>
            <div className="contact-channel">
              <span className="contact-channel-icon" aria-hidden="true">
                <Icon name={channel.icon} size={16} />
              </span>
              <div className="contact-channel-body">
                <p className="text-label">{channel.label}</p>
                {/* Not a 'mailto:' link while the address is a placeholder:
                    a link that opens a compose window for an address nobody
                    reads is worse than plain text that says so. */}
                <p className={channel.placeholder ? "text-body text-faint" : "text-body"}>
                  {channel.detail}
                  {channel.placeholder ? (
                    <span className="visually-hidden"> (placeholder)</span>
                  ) : null}
                </p>
              </div>
              {channel.placeholder ? <span className="text-micro">Placeholder</span> : null}
            </div>
          </Reveal>
        ))}
      </div>

      <div className="contact-note">
        <p className="text-caption">{CONTACT.responseExpectation}</p>
      </div>
    </Container>
  );
}
