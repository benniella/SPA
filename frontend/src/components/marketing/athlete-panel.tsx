"use client";

import { motion, useReducedMotion } from "motion/react";

import { AnimatedMetricValue, MOTION } from "@/components/motion/primitives";
import { IllustrativeTag } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { ILLUSTRATIVE_NOTE, PERFORMANCE_METRICS } from "@/data/marketing";

interface IllustratedMetric {
  readonly id: string;
  readonly value: string;
  readonly magnitude: number;
}

const ILLUSTRATED: readonly IllustratedMetric[] = [
  { id: "speed", value: "24.1", magnitude: 0.72 },
  { id: "distance", value: "1,284", magnitude: 0.55 },
  { id: "acceleration", value: "3.4", magnitude: 0.4 },
  { id: "position", value: "RB", magnitude: 0.62 },
  { id: "workload", value: "68", magnitude: 0.68 },
  { id: "movement", value: "14", magnitude: 0.48 },
];

const TRACE: readonly { readonly x: number; readonly y: number }[] = [
  { x: 24, y: 150 },
  { x: 48, y: 132 },
  { x: 76, y: 118 },
  { x: 108, y: 116 },
  { x: 140, y: 100 },
  { x: 172, y: 72 },
  { x: 200, y: 44 },
  { x: 224, y: 26 },
];

export function AthletePerformancePanel() {
  const reduced = useReducedMotion();

  return (
    <div className="viz-frame">
      <div className="viz-header">
        <span className="row-center">
          <Icon name="motion" size={14} />
          <span className="text-label">Player metrics</span>
        </span>
        <IllustrativeTag />
      </div>

      <div className="athlete-panel">
        <figure className="athlete-trace" style={{ margin: 0 }}>
          <svg
            className="viz-canvas"
            viewBox="0 0 250 180"
            role="img"
            aria-label="Illustrative single-player movement trace on a calibrated pitch surface, showing a run with a change of direction."
          >
            <rect width="250" height="180" fill="var(--viz-surface)" />

            <g stroke="var(--viz-grid)" strokeWidth="1" strokeDasharray="2 6" opacity="0.75">
              {[62, 124, 186].map((x) => (
                <line key={x} x1={x} y1={0} x2={x} y2={180} />
              ))}
              {[45, 90, 135].map((y) => (
                <line key={y} x1={0} y1={y} x2={250} y2={y} />
              ))}
            </g>

            <motion.path
              d={smoothPath(TRACE)}
              fill="none"
              stroke="var(--color-accent)"
              strokeWidth="1.75"
              strokeLinecap="round"
              strokeLinejoin="round"
              initial={reduced ? { pathLength: 1 } : { pathLength: 0 }}
              whileInView={{ pathLength: 1 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: MOTION.duration.reveal * 2, ease: MOTION.easeOut }}
            />

            {/* Segment markers: the change-of-direction points, which are what a
                coach actually looks for in a trace. */}
            {TRACE.slice(1, -1).map((point, index) => (
              <motion.circle
                key={`${point.x}-${point.y}`}
                cx={point.x}
                cy={point.y}
                r={1.8}
                fill="var(--color-accent-secondary)"
                initial={reduced ? { opacity: 1 } : { opacity: 0 }}
                whileInView={{ opacity: 0.85 }}
                viewport={{ once: true, amount: 0.4 }}
                transition={{ duration: MOTION.duration.base, delay: 0.3 + index * 0.08 }}
              />
            ))}

            <circle
              cx={TRACE[0]?.x ?? 0}
              cy={TRACE[0]?.y ?? 0}
              r={3}
              fill="none"
              stroke="var(--color-foreground-muted)"
              strokeWidth="1.5"
            />
            <circle
              cx={TRACE[TRACE.length - 1]?.x ?? 0}
              cy={TRACE[TRACE.length - 1]?.y ?? 0}
              r={3.5}
              fill="var(--color-accent)"
            />

            <text
              x="10"
              y="170"
              fill="var(--color-foreground-faint)"
              fontFamily="var(--font-mono)"
              fontSize="9"
            >
              movement trace · 1 player
            </text>
          </svg>
        </figure>

        <div className="athlete-metrics">
          <dl className="athlete-metric-list">
            {PERFORMANCE_METRICS.map((metric, index) => {
              const illustrated = ILLUSTRATED.find((item) => item.id === metric.id);
              if (!illustrated) return null;

              const highlight = metric.id === "speed";

              return (
                <motion.div
                  key={metric.id}
                  className="athlete-metric"
                  initial={reduced ? { opacity: 1 } : { opacity: 0, y: 6 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.3 }}
                  transition={{
                    duration: MOTION.duration.base,
                    ease: MOTION.easeOut,
                    delay: index * 0.05,
                  }}
                >
                  <dt className="text-micro">{metric.label}</dt>
                  <dd className="athlete-metric-value">
                    <span className={highlight ? "text-accent" : undefined}>
                      {highlight ? (
                        <AnimatedMetricValue value={illustrated.value} />
                      ) : (
                        illustrated.value
                      )}
                    </span>
                    {metric.unit ? <span className="metric-unit">{metric.unit}</span> : null}
                  </dd>
                  <div className="metric-bar" aria-hidden="true">
                    <motion.div
                      className="metric-bar-fill"
                      initial={reduced ? { scaleX: illustrated.magnitude } : { scaleX: 0 }}
                      whileInView={{ scaleX: illustrated.magnitude }}
                      viewport={{ once: true, amount: 0.3 }}
                      transition={{
                        duration: MOTION.duration.slow,
                        ease: MOTION.easeOut,
                        delay: 0.15 + index * 0.05,
                      }}
                    />
                  </div>
                </motion.div>
              );
            })}
          </dl>

          <p className="text-caption athlete-panel-note">
            Worked example values, shown to illustrate the metric families SPA is designed to
            report. They are not output from a real analysis.
          </p>
        </div>
      </div>

      {/* Table-equivalent of the panel, so the illustrative status reaches
          assistive technology even when the visible note is truncated. */}
      <p className="visually-hidden">{ILLUSTRATIVE_NOTE}</p>
    </div>
  );
}

function smoothPath(points: readonly { readonly x: number; readonly y: number }[]): string {
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
