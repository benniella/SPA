import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button, ButtonLink, buttonClasses, type ButtonVariant } from "@/components/ui/button";

const VARIANTS: readonly ButtonVariant[] = ["primary", "technical", "ai"];

describe("buttonClasses", () => {
  it("supports exactly the three SPA variants", () => {
    for (const variant of VARIANTS) {
      const classes = buttonClasses({ variant });
      expect(classes).toContain("spa-button");
      expect(classes).toContain(`spa-button--${variant}`);
    }
  });

  it("uses the primary variant by default", () => {
    expect(buttonClasses({})).toContain("spa-button--primary");
  });

  it("treats fullWidth as an alias of block", () => {
    expect(buttonClasses({ fullWidth: true })).toContain("spa-button--block");
    expect(buttonClasses({ block: true })).toContain("spa-button--block");
  });

  it("marks only the arrowless buttons, which are the ones that draw the rail", () => {
    expect(buttonClasses({ arrow: false })).toContain("spa-button--arrowless");
    expect(buttonClasses({})).not.toContain("spa-button--arrowless");
  });
});

describe("Button", () => {
  it("renders every variant with the shared button geometry", () => {
    const { container } = render(
      <>
        {VARIANTS.map((variant) => (
          <Button key={variant} variant={variant}>
            {variant}
          </Button>
        ))}
      </>,
    );

    expect(container.querySelectorAll(".spa-button")).toHaveLength(3);
    expect(container.querySelectorAll(".spa-button__content")).toHaveLength(3);
    expect(container.querySelectorAll(".spa-button__rail")).toHaveLength(0);
  });

  it("does not fire when disabled, but stays reachable", async () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Create match
      </Button>,
    );

    const control = screen.getByRole("button", { name: "Create match" });
    expect(control).toBeDisabled();
    expect(control).toHaveAttribute("aria-disabled", "true");

    await userEvent.click(control);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("blocks interaction and announces itself while loading", async () => {
    const onClick = vi.fn();
    render(
      <Button loading loadingLabel="Starting analysis" onClick={onClick}>
        Start Analysis
      </Button>,
    );

    const control = screen.getByRole("button", { name: /Start Analysis/ });
    expect(control).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Starting analysis")).toBeInTheDocument();

    await userEvent.click(control);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("places a trailing icon after the label", () => {
    const { container } = render(
      <Button icon={<span data-testid="icon" />} iconPosition="trailing">
        View Report
      </Button>,
    );

    const label = container.querySelector(".spa-button__label");
    const icon = container.querySelector(".spa-button__icon");
    expect(label).toBeInTheDocument();
    expect(icon).toBeInTheDocument();
    expect(label?.compareDocumentPosition(icon as Node)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });
});

describe("ButtonLink", () => {
  it("does not navigate while loading", async () => {
    render(
      <ButtonLink href="/teams" loading loadingLabel="Opening teams">
        View Teams
      </ButtonLink>,
    );

    const link = screen.getByRole("link", { name: /View Teams/ });
    expect(link).toHaveAttribute("aria-busy", "true");

    const click = new MouseEvent("click", { bubbles: true, cancelable: true });
    const notPrevented = link.dispatchEvent(click);
    expect(notPrevented).toBe(false);
  });

  it("leaves navigation intact when not loading", () => {
    render(<ButtonLink href="/teams">View Teams</ButtonLink>);

    const link = screen.getByRole("link", { name: "View Teams" });
    expect(link).not.toHaveAttribute("aria-busy");
    expect(link).toHaveAttribute("href", "/teams");
  });
});
