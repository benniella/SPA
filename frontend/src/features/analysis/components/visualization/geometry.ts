import type { DensityGrid, RunVisualization, SourceFrame } from "@/types/api";

/** A source-frame rectangle: (left, top, width, height) in source pixels. */
export interface FrameExtent {
  readonly left: number;
  readonly top: number;
  readonly width: number;
  readonly height: number;
}

export function frameExtent(visualization: RunVisualization): FrameExtent {
  const [left, top, right, bottom] = visualization.density.bounds;
  const width = right - left || 1;
  const height = bottom - top || 1;
  return { left, top, width, height };
}

export function frameLabel(frame: SourceFrame): string {
  if (frame.width === null || frame.height === null) return "Observed coordinate bounds";
  return `${frame.width.toLocaleString()} × ${frame.height.toLocaleString()} px`;
}

export function pathData(points: readonly { x: number; y: number }[]): string {
  if (points.length === 0) return "";
  const [first, ...rest] = points;
  if (!first) return "";
  let d = `M ${round(first.x)} ${round(first.y)}`;
  for (const point of rest) {
    d += ` L ${round(point.x)} ${round(point.y)}`;
  }
  return d;
}

/** Normalized 0–1 intensity per grid cell, row-major. */
export function cellIntensities(grid: DensityGrid): number[] {
  if (grid.max_count <= 0) return grid.counts.map(() => 0);
  return grid.counts.map((count) => count / grid.max_count);
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}
