import type { ReactNode } from "react";

import { Container } from "@/components/ui/section";

export interface AppPageHeaderProps {
  readonly id?: string;
  readonly title: string;
  readonly description?: string;
  readonly actions?: ReactNode;
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

export function AppPageBody({ children }: { children: ReactNode }) {
  return (
    <Container>
      <div className="app-page-body">{children}</div>
    </Container>
  );
}
