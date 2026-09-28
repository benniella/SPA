import Link from "next/link";

import { BrandMark } from "@/components/brand/brand-mark";
import { Reveal, StaggerGroup, StaggerItem } from "@/components/motion/primitives";
import { Icon } from "@/components/ui/icon";
import { FOOTER_COLUMNS, FOOTER_LEGAL, NAV_ACTIONS } from "@/data/marketing";

export function Footer() {
  return (
    <footer className="footer">
      <div className="container-page">
        <StaggerGroup as="div" className="footer-grid">
          <StaggerItem as="div">
            <div className="stack stack-4">
              <BrandMark variant="full" />
              <p className="text-body" style={{ maxWidth: "32ch" }}>
                Turn sports video into performance data.
              </p>
              <div>
                <Link href={NAV_ACTIONS.primary.href} className="footer-link row-center">
                  {NAV_ACTIONS.primary.label}
                  <Icon name="arrow-right" size={14} />
                </Link>
              </div>
            </div>
          </StaggerItem>

          {FOOTER_COLUMNS.map((column) => (
            <StaggerItem key={column.id} as="div">
              <nav aria-labelledby={`footer-${column.id}`} className="stack stack-3">
                <h2 id={`footer-${column.id}`} className="footer-column-heading">
                  {column.heading}
                </h2>
                <ul className="stack stack-2">
                  {column.links.map((link) => (
                    <li key={link.label}>
                      <FooterLink href={link.href}>{link.label}</FooterLink>
                    </li>
                  ))}
                </ul>
              </nav>
            </StaggerItem>
          ))}
        </StaggerGroup>

        <Reveal from="none">
          <div className="footer-legal">
            <div className="row-between">
              <p className="text-caption">{FOOTER_LEGAL.copyright}</p>
              <p className="text-caption">{FOOTER_LEGAL.note}</p>
            </div>
          </div>
        </Reveal>
      </div>
    </footer>
  );
}

function FooterLink({ href, children }: { href: string; children: React.ReactNode }) {
  const isExternal = /^https?:\/\//.test(href);
  const isAnchor = href.startsWith("#");

  if (isExternal || isAnchor) {
    return (
      <a
        className="footer-link"
        href={href}
        {...(isExternal ? { rel: "noreferrer noopener" } : {})}
      >
        {children}
      </a>
    );
  }

  return (
    <Link className="footer-link" href={href}>
      {children}
    </Link>
  );
}
