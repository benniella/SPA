"use client";

import { motion, useReducedMotion } from "motion/react";

import { MOTION } from "@/components/motion/primitives";
import { IllustrativeTag } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import type { IconName } from "@/data/marketing";
import { ENGINE_STAGES, ILLUSTRATIVE_NOTE } from "@/data/marketing";

interface FrameFigure {
  readonly id: string;
  readonly startX: number;
  readonly startY: number;
  readonly dx: number;
  readonly dy: number;
  readonly offset: number;
}

const FRAME_FIGURES: readonly FrameFigure[] = [
  { id: "a", startX: 26, startY: 74, dx: 4.5, dy: -1.2, offset: 0 },
  { id: "b", startX: 54, startY: 62, dx: -3.5, dy: 1.1, offset: 1 },
  { id: "c", startX: 82, startY: 82, dx: 3.8, dy: -1.6, offset: 2 },
  { id: "d", startX: 112, startY: 58, dx: -4.2, dy: 1.4, offset: 0.5 },
  { id: "e", startX: 142, startY: 78, dx: 3.2, dy: -1, offset: 1.6 },
  { id: "f", startX: 172, startY: 66, dx: -3.6, dy: 1.3, offset: 2.4 },
];

function figureAt(figure: FrameFigure, frame: number): { readonly x: number; readonly y: number } {
  const travelled = frame + figure.offset;
  return {
    x: figure.startX + figure.dx * travelled,
    y: figure.startY + figure.dy * travelled,
  };
}

/* A player seen from broadcast distance: head, torso and two legs, with a slight
   stance. Recognisable as a person at this size, which a circle over a bar is
   not, and still a silhouette rather than a photograph. */
function Figure({ x, y }: { readonly x: number; readonly y: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <circle cx="0" cy="-8.4" r="2.6" />
      <rect x="-2.5" y="-5.6" width="5" height="7.4" rx="1.9" />
      <path d="M-2 2.2 -3.8 8 M2 2.2 3.8 8" fill="none" strokeWidth="1.7" strokeLinecap="round" />
    </g>
  );
}

/* The tracking panel's scope is the whole recording rather than one frame, so it
   shows more subjects than a single frame can hold — the four the detector
   followed through this passage of play. Each id and confidence is illustrative. */
const TRACKED_SUBJECTS: readonly {
  readonly id: string;
  readonly confidence: string;
}[] = [
  { id: "07", confidence: "0.94" },
  { id: "04", confidence: "0.91" },
  { id: "11", confidence: "0.88" },
  { id: "18", confidence: "0.86" },
];

/* Performance readouts produced once tracked positions become measurements.
   Illustrative values for one analysed passage of play. */
const PERFORMANCE_METRICS: readonly {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly unit: string;
  readonly status?: boolean;
}[] = [
  { id: "speed", label: "Speed", value: "24.8", unit: "km/h" },
  { id: "distance", label: "Distance", value: "8.4", unit: "km" },
  { id: "acceleration", label: "Acceleration", value: "3.7", unit: "m/s²" },
  { id: "workload", label: "Workload", value: "High", unit: "", status: true },
];

/* One row per tracked subject: the identity the tracking stage assigned, and the
   performance figures computed from it. Illustrative values. */
const STRUCTURED_ROWS: readonly {
  readonly id: string;
  readonly speed: string;
  readonly distance: string;
  readonly workload: string;
}[] = [
  { id: "ID 07", speed: "24.8 km/h", distance: "8.4 km", workload: "high" },
  { id: "ID 04", speed: "22.1 km/h", distance: "7.9 km", workload: "high" },
  { id: "ID 11", speed: "19.6 km/h", distance: "6.7 km", workload: "moderate" },
  { id: "ID 18", speed: "21.4 km/h", distance: "7.2 km", workload: "moderate" },
  { id: "ID 09", speed: "17.2 km/h", distance: "5.8 km", workload: "moderate" },
  { id: "ID 02", speed: "15.9 km/h", distance: "4.6 km", workload: "low" },
];

export function VideoPerformanceVisualization() {
  const reduced = useReducedMotion();

  return (
    <section
      className="spa-analysis-visual"
      aria-label="SPA analysis pipeline: video input, detection and tracking, performance data"
    >
      <div className="spa-analysis-panel spa-analysis-panel--input">
        <div className="spa-analysis-panel__header">
          <span className="spa-analysis-panel__title">Video input</span>
          <span className="spa-analysis-panel__status">
            <span className="spa-status-dot" aria-hidden="true" />
            Raw
          </span>
        </div>

        <div className="spa-video-frames">
          {[0, 1, 2, 3].map((frame) => (
            <div key={frame} className="spa-video-frame">
              <svg
                className="spa-video-canvas"
                viewBox="0 0 200 110"
                preserveAspectRatio="xMidYMid slice"
                role="img"
                aria-label={`Illustrative raw frame ${frame + 1} of 4: a pitch with player silhouettes, before any detection.`}
              >
                <defs>
                  <linearGradient id={`spa-grass-${frame}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stopColor="var(--viz-pitch-far)" />
                    <stop offset="1" stopColor="var(--viz-pitch-near)" />
                  </linearGradient>
                </defs>

                {/* Footage as recorded: a pitch receding to the far touchline,
                    with the halfway line and centre circle for perspective. */}
                <rect width="200" height="110" fill={`url(#spa-grass-${frame})`} />
                <g stroke="var(--viz-pitch-mark)" strokeWidth="0.9" opacity="0.55">
                  <line x1="0" y1="30" x2="200" y2="30" />
                  <line x1="100" y1="30" x2="100" y2="110" />
                  <circle cx="100" cy="30" r="16" fill="none" />
                </g>

                {/* Ungrouped human shapes — footage as recorded, before any
                    detection. Deliberately without boxes or labels: the absence
                    is the point the next stage contrasts against. Each figure
                    moves on its own across the four frames, so the sequence
                    reads as play rather than one drawing repeated. */}
                <g fill="var(--viz-player)" opacity="0.85">
                  {FRAME_FIGURES.map((figure) => {
                    const { x, y } = figureAt(figure, frame);
                    return <Figure key={figure.id} x={x} y={y} />;
                  })}
                </g>

                <rect
                  width="200"
                  height="110"
                  fill="none"
                  stroke="var(--color-border)"
                  strokeWidth="1"
                />
              </svg>
            </div>
          ))}
        </div>

        <div className="spa-analysis-panel__footer">
          <span>Source</span>
          <strong>Sports footage</strong>
          <span className="spa-footer-spacer" />
          <span>Recording</span>
          <strong>PROBLEM.movements</strong>
        </div>
      </div>

      {/* PIPELINE CONNECTOR */}
      <div className="spa-analysis-connector" aria-hidden="true">
        <span className="spa-analysis-connector__line" />
        <span className="spa-analysis-connector__arrow">↓</span>
      </div>

      {/* =========================================================
          STAGE 02 — DETECTION + TRACKING
          ========================================================= */}
      <div className="spa-analysis-panel spa-analysis-panel--tracking">
        <div className="spa-analysis-panel__header">
          <span className="spa-analysis-panel__title">Detection + tracking</span>
          <span className="spa-analysis-badge">Analysing</span>
        </div>

        <div className="spa-tracking-space">
          <div className="spa-grid" aria-hidden="true" />

          {TRACKED_SUBJECTS.map((subject, index) => (
            <div
              // Position within the passage of play; fixed, so the four boxes
              // read as subjects at loose positions rather than a lattice.
              key={subject.id}
              className={`spa-track spa-track--0${index + 1}`}
              aria-label={`Illustrative tracked subject ${index + 1} of 4. Not measured from the source footage.`}
            >
              <div className="spa-track-box">
                <span className="spa-track-label">
                  ID {subject.id} · {subject.confidence}
                </span>
                <span className="spa-track-corner spa-track-corner--tl" />
                <span className="spa-track-corner spa-track-corner--tr" />
                <span className="spa-track-corner spa-track-corner--bl" />
                <span className="spa-track-corner spa-track-corner--br" />
              </div>
              <div className={`spa-trajectory spa-trajectory--0${index + 1}`} />
            </div>
          ))}
        </div>

        <div className="spa-analysis-panel__footer">
          <span>Detected</span>
          <strong>4 / 4</strong>
          <span className="spa-footer-divider" />
          <span>Tracked</span>
          <strong>Stable</strong>
          <span className="spa-footer-spacer" />
          <span>FPS</span>
          <strong>25</strong>
        </div>
      </div>

      {/* PIPELINE CONNECTOR */}
      <div className="spa-analysis-connector" aria-hidden="true">
        <span className="spa-analysis-connector__line" />
        <span className="spa-analysis-connector__arrow">↓</span>
      </div>

      {/* =========================================================
          STAGE 03 — PERFORMANCE DATA
          ========================================================= */}
      <div className="spa-analysis-panel spa-analysis-panel--performance">
        <div className="spa-analysis-panel__header">
          <span className="spa-analysis-panel__title">Performance data</span>
          <span className="spa-analysis-badge spa-analysis-badge--blue">Analysed</span>
        </div>

        <div className="spa-performance-grid">
          {PERFORMANCE_METRICS.map((metric, index) => (
            <motion.div
              key={metric.id}
              className="spa-metric"
              initial={reduced ? { opacity: 1 } : { opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: MOTION.duration.slow, delay: index * 0.06 }}
            >
              <span className="spa-metric__label">{metric.label}</span>
              <strong
                className={`spa-metric__value${metric.status ? "spa-metric__value--status" : ""}`}
              >
                {metric.value}
                {metric.unit ? <small> {metric.unit}</small> : null}
              </strong>
            </motion.div>
          ))}
        </div>

        <div className="spa-performance-flow">
          <span>Detected</span>
          <span aria-hidden="true">→</span>
          <span>Tracked</span>
          <span aria-hidden="true">→</span>
          <span>Measured</span>
          <span aria-hidden="true">→</span>
          <strong>Analysed</strong>
        </div>

        {/* The overlay above is a drawing, not a measurement of the footage it
            sits beside. Said once, in the panel that carries the numbers, and
            overridden for assistive technology because the badge's own label is
            abbreviated when it is shown on screen. */}
        <p className="spa-analysis-note" aria-label={ILLUSTRATIVE_NOTE}>
          <IllustrativeTag variant="full" />
        </p>
      </div>
    </section>
  );
}

export function StructuredOutputVisualization() {
  const reduced = useReducedMotion();

  return (
    <div className="viz-frame">
      <div className="viz-header">
        <span className="row-center">
          <Icon name="analytics" size={14} />
          <span className="text-label">Performance data</span>
        </span>
        <IllustrativeTag />
      </div>

      <div style={{ overflowX: "auto" }}>
        <table
          style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--font-size-small)" }}
        >
          <caption className="visually-hidden">
            Illustrative example of the performance figures computed for each tracked subject.
          </caption>
          <thead>
            <tr>
              <Th>Subject</Th>
              <Th>Speed</Th>
              <Th>Distance</Th>
              <Th>Workload</Th>
            </tr>
          </thead>
          <tbody>
            {STRUCTURED_ROWS.map((row, index) => (
              <motion.tr
                key={row.id}
                initial={reduced ? { opacity: 1 } : { opacity: 0, x: -6 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, amount: 0.5 }}
                transition={{ duration: MOTION.duration.base, delay: index * 0.05 }}
                style={{ borderTop: "1px solid var(--color-border)" }}
              >
                <Td>
                  <span className="viz-readout-value">{row.id}</span>
                </Td>
                <Td>
                  <span className="viz-readout-value">{row.speed}</span>
                </Td>
                <Td>
                  <span className="viz-readout-value">{row.distance}</span>
                </Td>
                <Td>
                  <span className="text-caption">{row.workload}</span>
                </Td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-caption" style={{ padding: "var(--space-3) var(--space-4)" }}>
        Every row keeps the track identity that produced it, so a performance figure can always be
        traced back to the footage it came from.
      </p>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th
      scope="col"
      className="text-micro"
      style={{
        textAlign: "left",
        padding: "var(--space-3) var(--space-4)",
        fontWeight: "var(--font-weight-medium)",
        background: "var(--color-surface)",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </th>
  );
}

function Td({ children }: { children: React.ReactNode }) {
  return (
    <td style={{ padding: "var(--space-3) var(--space-4)", verticalAlign: "baseline" }}>
      {children}
    </td>
  );
}

export function EnginePipelineVisualization() {
  const reduced = useReducedMotion();
  const visionCount = ENGINE_STAGES.filter((stage) => stage.kind === "vision").length;

  return (
    <div className="viz-frame">
      <div className="viz-header">
        <span className="row-center">
          <Icon name="ai" size={14} />
          <span className="text-label">Analysis pipeline</span>
        </span>
        <span className="row-center">
          <IllustrativeTag />
          <span className="text-micro">left to right</span>
        </span>
      </div>

      <div style={{ padding: "var(--space-5)" }}>
        {/* The rail. Horizontal on desktop, wrapped on narrow screens — the
            stage count does not change, only how many fit on a row. */}
        <ol className="engine-rail">
          {ENGINE_STAGES.map((stage, index) => (
            <motion.li
              key={stage.id}
              className="engine-stage"
              data-kind={stage.kind}
              initial={reduced ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{
                duration: MOTION.duration.slow,
                ease: MOTION.easeOut,
                delay: index * 0.05,
              }}
            >
              <span className="engine-stage-number" aria-hidden="true">
                {index + 1}
              </span>
              <span className="engine-stage-icon">
                <Icon name={stage.icon as IconName} size={16} />
              </span>
              <span className="engine-stage-label">{stage.label}</span>
              <span className="engine-stage-output">{stage.output}</span>
            </motion.li>
          ))}
        </ol>

        <div className="engine-legend">
          <span className="row-center">
            <span className="engine-legend-mark" data-kind="vision" />
            <span className="text-micro">
              Stages 1–{visionCount} — model-driven computer vision
            </span>
          </span>
          <span className="row-center">
            <span className="engine-legend-mark" data-kind="analysis" />
            <span className="text-micro">
              Stages {visionCount + 1}–{ENGINE_STAGES.length} — computation over tracking data
            </span>
          </span>
        </div>
      </div>
    </div>
  );
}
