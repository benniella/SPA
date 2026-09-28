"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";

import { MOTION } from "@/components/motion/primitives";
import { IllustrativeTag } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { Tabs } from "@/components/ui/tabs";
import { ANALYSIS_VIEWS } from "@/data/marketing";

const PITCH = { length: 105, width: 68 } as const;

const MARGIN = 10;

const PENALTY_AREA = { depth: 16.5, width: 40.32 } as const;
const GOAL_AREA = { depth: 5.5, width: 18.32 } as const;
const CENTRE_CIRCLE_RADIUS = 9.15;

const VIEW_BOX = `${-MARGIN} ${-MARGIN} ${PITCH.length + MARGIN * 2} ${PITCH.width + MARGIN * 2}`;

interface Point {
  readonly x: number;
  readonly y: number;
}

const TRAJECTORIES: readonly { readonly id: number; readonly points: readonly Point[] }[] = [
  {
    id: 1,
    points: [
      { x: 18, y: 46 },
      { x: 28, y: 40 },
      { x: 39, y: 33 },
      { x: 50, y: 29 },
      { x: 62, y: 26 },
      { x: 74, y: 24 },
    ],
  },
  {
    id: 2,
    points: [
      { x: 22, y: 22 },
      { x: 34, y: 24 },
      { x: 47, y: 28 },
      { x: 58, y: 34 },
      { x: 68, y: 42 },
      { x: 78, y: 50 },
    ],
  },
  {
    id: 3,
    points: [
      { x: 12, y: 34 },
      { x: 26, y: 44 },
      { x: 40, y: 48 },
      { x: 55, y: 46 },
      { x: 70, y: 40 },
      { x: 88, y: 36 },
    ],
  },
  {
    id: 4,
    points: [
      { x: 30, y: 60 },
      { x: 44, y: 56 },
      { x: 56, y: 48 },
      { x: 66, y: 38 },
      { x: 76, y: 30 },
    ],
  },
  {
    id: 5,
    points: [
      { x: 86, y: 18 },
      { x: 74, y: 22 },
      { x: 62, y: 28 },
      { x: 52, y: 36 },
      { x: 44, y: 46 },
    ],
  },
];

/** Relative weights 0–1, shaped into one hot zone in the left half-space and a
 * secondary one in the right wide channel. */
const HEATMAP_COLUMNS = 14;
const HEATMAP_ROWS = 9;

const HEATMAP_CELLS: readonly number[] = [
  0.0, 0.05, 0.12, 0.2, 0.14, 0.06, 0.0, 0.0, 0.04, 0.1, 0.16, 0.1, 0.04, 0.0, 0.06, 0.18, 0.42,
  0.55, 0.3, 0.12, 0.02, 0.05, 0.14, 0.26, 0.2, 0.08, 0.0, 0.0, 0.1, 0.3, 0.72, 0.88, 0.5, 0.2,
  0.06, 0.12, 0.24, 0.34, 0.2, 0.04, 0.0, 0.02, 0.12, 0.34, 0.76, 0.94, 0.62, 0.26, 0.1, 0.2, 0.3,
  0.24, 0.1, 0.0, 0.0, 0.08, 0.2, 0.4, 0.62, 0.44, 0.24, 0.12, 0.26, 0.22, 0.12, 0.02, 0.0, 0.0,
  0.04, 0.1, 0.22, 0.34, 0.3, 0.18, 0.1, 0.05, 0.1, 0.08, 0.02, 0.0, 0.0, 0.02, 0.06, 0.12, 0.1,
  0.06, 0.03, 0.0, 0.0, 0.0, 0.02, 0.0, 0.0, 0.0, 0.0, 0.0, 0.01, 0.02, 0.03, 0.02, 0.0, 0.0, 0.0,
  0.0, 0.04, 0.03, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
  0.0,
];

/** Team shape at one instant: ten outfield positions plus a goalkeeper. */
const SHAPE = {
  home: [
    { x: 8, y: 34 },
    { x: 24, y: 12 },
    { x: 26, y: 28 },
    { x: 26, y: 44 },
    { x: 30, y: 58 },
    { x: 46, y: 18 },
    { x: 48, y: 34 },
    { x: 50, y: 50 },
    { x: 62, y: 24 },
    { x: 64, y: 44 },
    { x: 58, y: 34 },
  ],
  away: [
    { x: 97, y: 34 },
    { x: 84, y: 20 },
    { x: 82, y: 34 },
    { x: 84, y: 48 },
    { x: 80, y: 60 },
    { x: 70, y: 24 },
    { x: 68, y: 38 },
    { x: 70, y: 52 },
    { x: 58, y: 30 },
    { x: 56, y: 46 },
    { x: 66, y: 12 },
  ],
} as const satisfies Record<"home" | "away", readonly Point[]>;

/** Timed incidents, placed where they occurred. */
const EVENTS: readonly {
  readonly id: string;
  readonly point: Point;
  readonly kind: string;
}[] = [
  { id: "1", point: { x: 32, y: 40 }, kind: "Sprint" },
  { id: "2", point: { x: 54, y: 28 }, kind: "Pass" },
  { id: "3", point: { x: 72, y: 26 }, kind: "Carry" },
  { id: "4", point: { x: 66, y: 44 }, kind: "Press" },
  { id: "5", point: { x: 89, y: 34 }, kind: "Shot" },
];

/** Number of views the pitch visualization offers, for the section copy. */
export const PITCH_VIEW_COUNT = ANALYSIS_VIEWS.length;

export function PitchVisualization() {
  const items = ANALYSIS_VIEWS.map((view) => ({
    id: view.id,
    label: view.label,
    content: <ViewPanel view={view.id} />,
  }));

  return (
    <div className="viz-frame">
      <div className="viz-header">
        <span className="row-center">
          <Icon name="sport" size={14} />
          <span className="text-label">Pitch analysis</span>
        </span>
        <span className="row-center">
          <IllustrativeTag />
          <span className="text-micro">105 × 68 m · pitch space</span>
        </span>
      </div>

      <div style={{ padding: "var(--space-5)" }}>
        <Tabs items={items} label="Pitch analysis view" />
      </div>
    </div>
  );
}

function ViewPanel({ view }: { view: string }) {
  return (
    <div className="stack stack-4">
      <svg
        className="viz-canvas"
        viewBox={VIEW_BOX}
        role="img"
        aria-label={ariaLabelFor(view)}
        preserveAspectRatio="xMidYMid meet"
        style={{
          background: "var(--viz-surface)",
          border: "1px solid var(--color-border)",
        }}
      >
        <Pitch />
        <AnimatePresence mode="wait" initial={false}>
          <motion.g
            key={view}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: MOTION.duration.base, ease: MOTION.easeOut }}
          >
            {view === "trajectory" ? <TrajectoryView /> : null}
            {view === "heatmap" ? <HeatmapView /> : null}
            {view === "shape" ? <ShapeView /> : null}
            {view === "events" ? <EventsView /> : null}
          </motion.g>
        </AnimatePresence>
      </svg>

      <div className="viz-readout">
        {readoutsFor(view).map((item) => (
          <span key={item.label} className="viz-readout-item">
            <span className="text-micro">{item.label}</span>
            <span className="viz-readout-value">{item.value}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/** Outline, halfway line, centre circle and both penalty and goal areas, drawn
 * from the metre constants so the markings stay correct if the space changes. */
function Pitch() {
  const { length: L, width: W } = PITCH;
  const pa = PENALTY_AREA;
  const ga = GOAL_AREA;

  return (
    <g
      fill="none"
      stroke="var(--viz-line)"
      strokeWidth="0.5"
      vectorEffect="non-scaling-stroke"
      opacity="0.85"
    >
      <rect x={0} y={0} width={L} height={W} />
      <line x1={L / 2} y1={0} x2={L / 2} y2={W} />
      <circle cx={L / 2} cy={W / 2} r={CENTRE_CIRCLE_RADIUS} />
      <circle cx={L / 2} cy={W / 2} r={0.6} fill="var(--color-border-strong)" />

      {/* Both ends. The right-hand pair use an explicit positive width and a
          `x' that is 'L - depth', rather than a negative width — a negative
          'width` is invalid SVG and React logs it as a console error on every
          render. */}
      <rect x={0} y={(W - pa.width) / 2} width={pa.depth} height={pa.width} />
      <rect x={0} y={(W - ga.width) / 2} width={ga.depth} height={ga.width} />
      <rect x={L - pa.depth} y={(W - pa.width) / 2} width={pa.depth} height={pa.width} />
      <rect x={L - ga.depth} y={(W - ga.width) / 2} width={ga.depth} height={ga.width} />
    </g>
  );
}

/** Movement: trajectories with direction, drawn in sequence. */
function TrajectoryView() {
  const reduced = useReducedMotion();

  return (
    <g>
      {TRAJECTORIES.map((trajectory, index) => {
        const first = trajectory.points[0];
        const last = trajectory.points[trajectory.points.length - 1];
        if (!first || !last) return null;

        return (
          <g key={trajectory.id}>
            <motion.path
              d={smoothPath(trajectory.points)}
              fill="none"
              stroke={index % 2 === 0 ? "var(--color-accent)" : "var(--color-accent-secondary)"}
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              vectorEffect="non-scaling-stroke"
              initial={reduced ? { pathLength: 1, opacity: 1 } : { pathLength: 0, opacity: 0.2 }}
              animate={{ pathLength: 1, opacity: index % 2 === 0 ? 0.95 : 0.65 }}
              transition={{
                duration: MOTION.duration.reveal * 1.6,
                ease: MOTION.easeOut,
                delay: index * 0.09,
              }}
            />
            {/* Start marker: hollow. */}
            <circle
              cx={first.x}
              cy={first.y}
              r={1.4}
              fill="none"
              stroke="var(--color-foreground-muted)"
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
            />
            {/* End marker: filled. The pair is what communicates direction —
                without it a path is just a line. */}
            <circle cx={last.x} cy={last.y} r={1.8} fill="var(--color-accent)" />
          </g>
        );
      })}
    </g>
  );
}

/** Density: a coarse grid, not a blur. */
function HeatmapView() {
  const cellWidth = PITCH.length / HEATMAP_COLUMNS;
  const cellHeight = PITCH.width / HEATMAP_ROWS;

  return (
    <g>
      {HEATMAP_CELLS.map((weight, index) => {
        if (weight <= 0) return null;

        const column = index % HEATMAP_COLUMNS;
        const row = Math.floor(index / HEATMAP_COLUMNS);

        return (
          <rect
            key={index}
            x={column * cellWidth}
            y={row * cellHeight}
            width={cellWidth}
            height={cellHeight}
            fill="var(--color-accent)"
            /* Opacity steps rather than a blur radius: it renders identically in
               every browser, costs nothing, and reads as a measured surface
               instead of a soft glow. */
            opacity={Math.min(0.75, weight * 0.8)}
          />
        );
      })}
    </g>
  );
}

/** Shape: two teams, distinguished by form as well as by colour. */
function ShapeView() {
  const reduced = useReducedMotion();

  return (
    <g>
      {/* Spacing envelope, drawn behind the players. This is the "compactness"
          the domain models, shown rather than asserted. */}
      <polygon
        points={convexHullPoints(SHAPE.home, 3)}
        fill="var(--color-accent)"
        fillOpacity="0.07"
        stroke="var(--color-accent-secondary)"
        strokeWidth="1"
        strokeDasharray="4 3"
        vectorEffect="non-scaling-stroke"
      />

      {SHAPE.home.map((point, index) => (
        <motion.g
          key={`home-${index}`}
          initial={reduced ? { opacity: 1 } : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: MOTION.duration.slow, delay: index * 0.02 }}
        >
          {/* Home: filled circle. */}
          <circle cx={point.x} cy={point.y} r={2.4} fill="var(--color-accent)" />
        </motion.g>
      ))}

      {SHAPE.away.map((point, index) => (
        <motion.g
          key={`away-${index}`}
          initial={reduced ? { opacity: 1 } : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: MOTION.duration.slow, delay: 0.15 + index * 0.02 }}
        >
          {/* Away: hollow square. Shape carries the difference, so the two teams
              are still distinguishable without colour. */}
          <rect
            x={point.x - 2}
            y={point.y - 2}
            width={4}
            height={4}
            fill="none"
            stroke="var(--color-foreground)"
            strokeWidth="1.25"
            vectorEffect="non-scaling-stroke"
          />
        </motion.g>
      ))}
    </g>
  );
}

/** Events: timed incidents at the position they occurred. */
function EventsView() {
  const reduced = useReducedMotion();

  return (
    <g>
      {EVENTS.map((event, index) => (
        <motion.g
          key={event.id}
          initial={reduced ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.6 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: MOTION.duration.slow, ease: MOTION.easeOut, delay: index * 0.07 }}
          style={{ transformOrigin: `${event.point.x}px ${event.point.y}px` }}
        >
          {/* A diamond: distinguishable from the circular detection markers
              used elsewhere on the page, so shape carries the meaning. */}
          <path
            d={`M${event.point.x} ${event.point.y - 3} L${event.point.x + 3} ${event.point.y} L${event.point.x} ${event.point.y + 3} L${event.point.x - 3} ${event.point.y} Z`}
            fill="var(--color-accent)"
          />
          <text
            x={event.point.x + 5}
            y={event.point.y + 2.5}
            fill="var(--color-foreground-muted)"
            fontFamily="var(--font-mono)"
            fontSize="3.4"
            letterSpacing="0.1"
          >
            {event.kind}
          </text>
        </motion.g>
      ))}
    </g>
  );
}

function ariaLabelFor(view: string): string {
  switch (view) {
    case "trajectory":
      return "Illustrative pitch view showing five player movement trajectories, each with a start and end marker.";
    case "heatmap":
      return "Illustrative pitch view showing spatial density as a grid of shaded cells, densest in the left half-space.";
    case "shape":
      return "Illustrative pitch view showing two teams` positions, with the home team's spacing envelope marked.";
    case "events":
      return "Illustrative pitch view showing timed performance events placed at their pitch positions.";
    default:
      return "Illustrative pitch analysis view.";
  }
}

function readoutsFor(view: string): readonly { readonly label: string; readonly value: string }[] {
  switch (view) {
    case "trajectory":
      return [
        { label: "Tracks", value: "5" },
        { label: "Space", value: "pitch" },
        { label: "Data", value: "illustrative" },
      ];
    case "heatmap":
      return [
        { label: "Grid", value: `${HEATMAP_COLUMNS} × ${HEATMAP_ROWS}` },
        { label: "Extent", value: "105 × 68 m" },
        { label: "Data", value: "illustrative" },
      ];
    case "shape":
      return [
        { label: "Players", value: "11 + 11" },
        { label: "Period", value: "instant" },
        { label: "Data", value: "illustrative" },
      ];
    case "events":
      return [
        { label: "Events", value: String(EVENTS.length) },
        { label: "Kind", value: "timed" },
        { label: "Data", value: "illustrative" },
      ];
    default:
      return [];
  }
}

/** Quadratic smoothing through midpoints, as in the hero frame. */
function smoothPath(points: readonly Point[]): string {
  const first = points[0];
  if (!first) return "";

  let d = `M ${first.x} ${first.y}`;

  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    if (!previous || !current) continue;

    const midX = (previous.x + current.x) / 2;
    const midY = (previous.y + current.y) / 2;
    d += ` Q ${previous.x} ${previous.y} ${midX} ${midY}`;
  }

  const last = points[points.length - 1];
  if (last && points.length > 1) d += ` L ${last.x} ${last.y}`;

  return d;
}

/** Padded envelope rather than a hard convex hull. */
function convexHullPoints(points: readonly Point[], padding: number): string {
  if (points.length === 0) return "";

  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs) - padding;
  const maxX = Math.max(...xs) + padding;
  const minY = Math.min(...ys) - padding;
  const maxY = Math.max(...ys) + padding;

  const cut = 8;

  return [
    `${minX + cut},${minY}`,
    `${maxX},${minY + cut}`,
    `${maxX},${maxY - cut}`,
    `${maxX - cut},${maxY}`,
    `${minX},${maxY - cut}`,
    `${minX},${minY + cut}`,
  ].join(" ");
}
