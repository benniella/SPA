import type { IconName } from "@/data/marketing";

const PATHS: Record<IconName, string> = {
  vision:
    "M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Zm9.5 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
  ai: "M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1m-8.6 8.6-2.1 2.1M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z",
  analytics: "M4 20V10m5 10V4m5 16v-7m5 7V7",
  sport:
    "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 0c2.5 2.4 3.8 5.5 3.8 9s-1.3 6.6-3.8 9m0-18c-2.5 2.4-3.8 5.5-3.8 9s1.3 6.6 3.8 9M3.4 9h17.2M3.4 15h17.2",
  video:
    "M3 7.5A1.5 1.5 0 0 1 4.5 6h9A1.5 1.5 0 0 1 15 7.5v9A1.5 1.5 0 0 1 13.5 18h-9A1.5 1.5 0 0 1 3 16.5v-9Zm12 3.2 5.2-2.9a.4.4 0 0 1 .6.35v7.7a.4.4 0 0 1-.6.35L15 13.3",
  motion: "M3 17c2.6 0 3.4-10 6-10s3.4 10 6 10 3.4-6 6-6",
  upload: "M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3",
  detect:
    "M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16M12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5Z",
  track: "M3 18c3 0 3-4 6-4s3-6 6-6 3 4 6 4M4.5 18a1.5 1.5 0 1 0 0-.01M19.5 12a1.5 1.5 0 1 0 0-.01",
  analyse: "M4 19V9m5 10V5m5 14v-6m5 6V8M3 21h18",
  understand: "M12 21s7-3.2 7-9V6.2L12 3 5 6.2V12c0 5.8 7 9 7 9Zm-2.6-9.4 1.9 1.9 3.5-3.9",
  "arrow-right": "M4 12h15m0 0-6-6m6 6-6 6",
  "arrow-down": "M12 4v15m0 0 6-6m-6 6-6-6",
  "chevron-up": "m5 15 7-7 7 7",
  "chevron-down": "m5 9 7 7 7-7",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 0c-4 0-7 2.4-7 6v2h14v-2c0-3.6-3-6-7-6Z",
  menu: "M4.5 7h15M4.5 12h15M4.5 17h9",
  close: "M6 6l12 12M18 6 6 18",
  eye: "M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Zm9.5 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
  "eye-off":
    "m3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 5.8A10.8 10.8 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a16 16 0 0 1-3.2 3.9M6.2 6.2C3.8 7.8 2.5 12 2.5 12s3.5 6.5 9.5 6.5a10 10 0 0 0 2.1-.2",
  play: "M8 5.5v13l11-6.5-11-6.5Z",
  check: "M5 12.5 9.5 17 19 7",
};

export interface IconProps {
  readonly name: IconName;
  readonly size?: number;
  readonly title?: string;
  readonly className?: string;
}

export function Icon({ name, size, title, className }: IconProps) {
  const labelled = typeof title === "string";

  return (
    <svg
      className={className}
      width={size ?? "1em"}
      height={size ?? "1em"}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={labelled ? undefined : true}
      role={labelled ? "img" : undefined}
      focusable="false"
    >
      {labelled ? <title>{title}</title> : null}
      <path d={PATHS[name]} />
    </svg>
  );
}

export function ButtonArrow() {
  return (
    <svg
      width="1em"
      height="1em"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS["arrow-right"]} />
    </svg>
  );
}
