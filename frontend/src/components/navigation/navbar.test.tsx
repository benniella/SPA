import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Navbar } from "@/components/navigation/navbar";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

function openMenu() {
  render(<Navbar />);
  fireEvent.click(screen.getByRole("button", { name: "Open navigation menu" }));
  return screen.getByRole("button", { name: "Dismiss navigation menu" });
}

function panel() {
  return document.querySelector(".nav-mobile") as HTMLElement;
}

// jsdom has no PointerEvent, so 'fireEvent.pointerDown' drops the coordinate and
// the gesture handlers see 'clientY === undefined'. A MouseEvent dispatched under
// the pointer type name carries the coordinate React reads.
function pointer(type: string, clientY: number) {
  const event = new MouseEvent(type, { clientY, bubbles: true });
  Object.defineProperty(event, "pointerId", { value: 1 });
  fireEvent(panel(), event);
}

/* The swipe-to-close gesture is driven by 'clientY' from a PointerEvent, which
   jsdom does not implement, so the coordinate is supplied by a MouseEvent. */
describe("Navbar mobile overlay", () => {
  it("closes from the toggle", () => {
    render(<Navbar />);
    fireEvent.click(screen.getByRole("button", { name: "Open navigation menu" }));
    fireEvent.click(screen.getByRole("button", { name: "Close navigation menu" }));
    expect(
      screen.queryByRole("button", { name: "Dismiss navigation menu" }),
    ).not.toBeInTheDocument();
  });

  it("closes on a backdrop tap", () => {
    const backdrop = openMenu();
    fireEvent.click(backdrop);
    expect(
      screen.queryByRole("button", { name: "Dismiss navigation menu" }),
    ).not.toBeInTheDocument();
  });

  it("closes when swiped upwards past the threshold", () => {
    openMenu();

    pointer("pointerdown", 400);
    pointer("pointermove", 320);

    expect(
      screen.queryByRole("button", { name: "Dismiss navigation menu" }),
    ).not.toBeInTheDocument();
  });

  it("stays open when a drag does not travel far enough", () => {
    openMenu();

    pointer("pointerdown", 400);
    pointer("pointermove", 380);
    pointer("pointerup", 380);

    expect(screen.getByRole("button", { name: "Dismiss navigation menu" })).toBeInTheDocument();
  });

  it("closes on release when the drag travelled far enough", () => {
    openMenu();

    pointer("pointerdown", 400);
    pointer("pointerup", 330);

    expect(
      screen.queryByRole("button", { name: "Dismiss navigation menu" }),
    ).not.toBeInTheDocument();
  });
});
