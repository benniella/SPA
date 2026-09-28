"use client";

import { motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useState } from "react";

import { HeroVideo } from "@/components/marketing/hero-video";
import { MOTION } from "@/components/motion/primitives";
import { IllustrativeTag } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { HERO_VIDEO, PROCESS_STEPS } from "@/data/marketing";

const FRAME_WIDTH = HERO_VIDEO.width;
const FRAME_HEIGHT = HERO_VIDEO.height;

/* The pitch grid is a calibration overlay, not a measurement of this clip. It is a
   plain projected grid with no player correspondence, which is what lets it be drawn
   over arbitrary footage without asserting anything about where a body is. */
const GRID_COLUMNS = 6;
const GRID_ROWS = 4;

/* Trajectory polylines are drawn as motion evidence only: they trace where activity
   crossed the frame, and deliberately carry no identity, no confidence and no box.
   They run through the grass and the upper frame, never across a subject, because a
   line crossing a player reads as that player's track - the correspondence this
   visual cannot support. */
const TRAJECTORIES: readonly (readonly { readonly x: number; readonly y: number }[])[] = [
  [
    { x: 10, y: 86 },
    { x: 150, y: 92 },
    { x: 292, y: 100 },
    { x: 434, y: 112 },
    { x: 574, y: 126 },
    { x: 714, y: 142 },
    { x: 854, y: 160 },
  ],
  [
    { x: 6, y: 424 },
    { x: 144, y: 418 },
    { x: 288, y: 414 },
    { x: 432, y: 412 },
    { x: 576, y: 414 },
    { x: 714, y: 418 },
    { x: 856, y: 424 },
  ],
  [
    { x: 18, y: 478 },
    { x: 160, y: 474 },
    { x: 304, y: 472 },
    { x: 448, y: 472 },
    { x: 592, y: 474 },
    { x: 730, y: 478 },
    { x: 858, y: 482 },
  ],
];

/* A sparse scatter of analysis activity across the frame. These are sample points
   for the detector's search density, not detected objects, so they are drawn as
   unlabelled marks rather than as boxes around anything. */
const ACTIVITY_POINTS: readonly { readonly x: number; readonly y: number; readonly weight: number }[] =
  [
    { x: 132, y: 214, weight: 0.5 },
    { x: 196, y: 176, weight: 0.75 },
    { x: 268, y: 344, weight: 0.9 },
    { x: 318, y: 262, weight: 1 },
    { x: 386, y: 196, weight: 0.6 },
    { x: 452, y: 312, weight: 0.85 },
    { x: 524, y: 232, weight: 0.7 },
    { x: 596, y: 356, weight: 0.55 },
    { x: 668, y: 288, weight: 0.8 },
    { x: 742, y: 208, weight: 0.65 },
  ];

/* The pitch-space origin, projected into the frame. Marks that need a coordinate
   reference anchor to it rather than to a player. */
const ORIGIN = { x: 432, y: 428 } as const;

/* The pipeline the hero frame is being read through. Taken from the platform's own
   stages rather than authored here, so the visual and the page cannot drift apart. */
const STAGES = PROCESS_STEPS.slice(0, 4).map((step) => step.label.toUpperCase());

/* The analysis runs at the footage's own rate; the counter and the readout report
   the same figure so they cannot disagree. */
const FPS = 30;

export function HeroAnalysisVisual() {
  const reduced = useReducedMotion();
  const [frame, setFrame] = useState(0);

  // A sampled frame counter, not a smooth timer: analysis is stepped.
  useEffect(() => {
    if (reduced) return;
    const id = window.setInterval(() => setFrame((value) => value + 4), 160);
    return () => window.clearInterval(id);
  }, [reduced]);

  const trails = useMemo(() => TRAJECTORIES.map((trail) => toPath(trail)), []);

  return (
    <figure className="hero-analysis">
      <div className="hero-analysis-body">
        <HeroVideo />

        <span className="hero-analysis-scanline" aria-hidden="true" />

        <svg
          className="hero-analysis-overlay"
          viewBox={`0 0 ${FRAME_WIDTH} ${FRAME_HEIGHT}`}
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
        >
          <PitchGrid />

          <g fill="none" strokeLinecap="round" strokeLinejoin="round">
            {trails.map((points, index) => (
              <motion.path
                key={points}
                d={points}
                stroke="var(--viz-detect)"
                strokeWidth="2"
                strokeOpacity={0.9 - index * 0.15}
                strokeDasharray="14 10"
                initial={reduced ? { pathLength: 1, opacity: 1 } : { pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{
                  duration: MOTION.duration.reveal * 2,
                  ease: MOTION.easeOut,
                  delay: 0.15 + index * 0.1,
                }}
              />
            ))}
          </g>

          <g>
            {ACTIVITY_POINTS.map((point, index) => (
              <motion.circle
                key={`${point.x}-${point.y}`}
                cx={point.x}
                cy={point.y}
                r={2 + point.weight * 2.5}
                fill="none"
                stroke="var(--viz-detect)"
                strokeWidth="1.25"
                strokeOpacity={0.25 + point.weight * 0.5}
                initial={reduced ? { opacity: 0.4 } : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{
                  duration: MOTION.duration.slow,
                  ease: MOTION.easeOut,
                  delay: 0.3 + index * 0.05,
                }}
              />
            ))}
          </g>

          <PitchOrigin />
        </svg>

        <div className="hero-analysis-chrome">
          <div className="hero-analysis-bar">
            <span className="row-center">
              <Icon name="detect" size={14} />
              <span className="text-label">Computer vision</span>
            </span>
            <span className="row-center">
              <IllustrativeTag />
              <span className="text-micro">Frame {String(frame).padStart(5, "0")}</span>
              <span className="text-micro">{FPS} fps</span>
            </span>
          </div>

          <div className="hero-analysis-foot">
            <div className="hero-analysis-pipeline">
              {STAGES.map((stage, index) => (
                <span key={stage} className="hero-analysis-stage">
                  {index > 0 ? (
                    <span className="hero-analysis-link" aria-hidden="true">
                      <Icon name="arrow-right" size={12} />
                    </span>
                  ) : null}
                  <span className="text-micro">{stage}</span>
                </span>
              ))}
            </div>
            <div className="hero-analysis-readout">
              <ReadoutItem label="Sample rate" value={`${FPS} fps`} />
              <ReadoutItem label="Frame" value={`${FRAME_WIDTH}×${FRAME_HEIGHT}`} />
              <ReadoutItem label="Pitch grid" value={`${GRID_COLUMNS}×${GRID_ROWS}`} />
              <ReadoutItem label="Status" value="analysing" />
            </div>
          </div>
        </div>
      </div>

      <figcaption className="visually-hidden">
        Sports footage with a projected pitch grid, movement trajectories and analysis
        readouts overlaid on the video.
      </figcaption>
    </figure>
  );
}

/** A projected pitch grid: calibration furniture, with no player correspondence. */
function PitchGrid() {
  const cellWidth = FRAME_WIDTH / GRID_COLUMNS;
  const cellHeight = FRAME_HEIGHT / GRID_ROWS;

  return (
    <g stroke="var(--viz-grid)" strokeWidth="1" opacity="0.8">
      {Array.from({ length: GRID_COLUMNS - 1 }, (_, index) => (
        <line
          key={`grid-v-${index}`}
          x1={cellWidth * (index + 1)}
          y1={0}
          x2={cellWidth * (index + 1)}
          y2={FRAME_HEIGHT}
        />
      ))}
      {Array.from({ length: GRID_ROWS - 1 }, (_, index) => (
        <line
          key={`grid-h-${index}`}
          x1={0}
          y1={cellHeight * (index + 1)}
          x2={FRAME_WIDTH}
          y2={cellHeight * (index + 1)}
        />
      ))}
    </g>
  );
}

/** The coordinate frame's origin: a crosshair and its axes, not a tracked object. */
function PitchOrigin() {
  return (
    <g stroke="var(--viz-detect)" strokeWidth="1" fill="none" opacity="0.7">
      <line x1={ORIGIN.x - 12} y1={ORIGIN.y} x2={ORIGIN.x + 12} y2={ORIGIN.y} />
      <line x1={ORIGIN.x} y1={ORIGIN.y - 12} x2={ORIGIN.x} y2={ORIGIN.y + 12} />
      <circle cx={ORIGIN.x} cy={ORIGIN.y} r={4} />
    </g>
  );
}

function ReadoutItem({ label, value }: { label: string; value: string }) {
  return (
    <span className="hero-analysis-readout-item">
      <span className="text-micro">{label}</span>
      <span className="hero-analysis-readout-value">{value}</span>
    </span>
  );
}

/** Smooths trail points with quadratic midpoint segments. */
function toPath(points: readonly { readonly x: number; readonly y: number }[]): string {
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
