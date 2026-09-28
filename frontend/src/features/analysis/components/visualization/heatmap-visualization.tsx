"use client";

import { useMemo, useState } from "react";

import { FrameSurface } from "@/features/analysis/components/visualization/frame-surface";
import {
  cellIntensities,
  frameExtent,
} from "@/features/analysis/components/visualization/geometry";
import type { RunVisualization } from "@/types/api";

interface HeatmapVisualizationProps {
  readonly visualization: RunVisualization;
  /** 'null' draws every track's density; a track id draws only that one. */
  readonly selectedTrackId: number | null;
}

/** Spatial density of observed positions over the source frame.
 *
 * The grid arrives aggregated from the API, so the browser draws at most a few
 * hundred rectangles rather than one element per observation. Intensity is a
 * single accent at stepped opacity */
export function HeatmapVisualization({
  visualization,
  selectedTrackId,
}: HeatmapVisualizationProps) {
  const extent = useMemo(() => frameExtent(visualization), [visualization]);
  const grid = visualization.density;
  const intensities = useMemo(() => cellIntensities(grid), [grid]);
  const [hovered, setHovered] = useState<number | null>(null);

  const cellWidth = grid.bounds[2] - grid.bounds[0] > 0 ? extent.width / grid.columns : 1;
  const cellHeight = grid.bounds[3] - grid.bounds[1] > 0 ? extent.height / grid.rows : 1;
  const hoveredCount = hovered === null ? null : (grid.counts[hovered] ?? 0);

  const label = `Spatial density of observed positions in source-video pixel space, ${grid.observation_count} observations over a ${grid.columns} by ${grid.rows} grid.`;

  return (
    <div className="stack stack-3">
      <FrameSurface extent={extent} label={label}>
        {intensities.map((intensity, index) => {
          if (intensity <= 0) return null;
          const column = index % grid.columns;
          const row = Math.floor(index / grid.columns);
          return (
            <rect
              key={index}
              x={grid.bounds[0] + column * cellWidth}
              y={grid.bounds[1] + row * cellHeight}
              width={cellWidth}
              height={cellHeight}
              fill="var(--color-accent)"
              opacity={0.12 + intensity * 0.78}
              onMouseEnter={() => setHovered(index)}
              onMouseLeave={() => setHovered(null)}
            />
          );
        })}
      </FrameSurface>

      <p className="text-caption" role="status">
        {hoveredCount === null
          ? `${grid.observation_count.toLocaleString()} observations from ${grid.track_count} track${grid.track_count === 1 ? "" : "s"}${
              selectedTrackId === null ? "" : ` — showing track ${selectedTrackId}`
            }.`
          : `${hoveredCount.toLocaleString()} observation${hoveredCount === 1 ? "" : "s"} in this cell.`}
      </p>
    </div>
  );
}
