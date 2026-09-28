import type { ReactNode } from "react";

import { Container } from "@/components/ui/section";

export interface AppPageHeaderProps {
  /** Anchor id for the page's own 'aria-labelledby', if it needs one. */
  readonly id?: string;
  /** The '<h1>'. One per page — this component is used once per route. */
  readonly title: string;
  /** A short context line: what this page is for, not marketing copy. */
  readonly description?: string;
  /** Page-level actions: create, filter, export. */
  readonly actions?: ReactNode;
  /** Breadcrumb or parent context, rendered above the title. */
  readonly breadcrumb?: ReactNode;
}

export function AppPageHeader({ id, title, description, actions, breadcrumb }: AppPageHeaderProps) {
  return (
    <Container>
      <div className="app-page-header">
        {breadcrumb ? <div className="breadcrumb">{breadcrumb}</div> : null}

        <div className="page-heading-row">
          <div className="app-page-header-copy">
            <h1 id={id} className="heading-page">
              {title}
            </h1>
            {description ? <p className="text-body app-page-header-lede">{description}</p> : null}
          </div>

          {actions ? <div className="app-page-header-actions">{actions}</div> : null}
        </div>
      </div>
    </Container>
  );
}

/** The application's content container: a page-width column with vertical rhythm. */
export function AppPageBody({ children }: { children: ReactNode }) {
  return (
    <Container>
      <div className="app-page-body">{children}</div>
    </Container>
  );
}
