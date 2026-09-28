"use client";

import { useMemo } from "react";

import { FrameSurface } from "@/features/analysis/components/visualization/frame-surface";
import { frameExtent, pathData } from "@/features/analysis/components/visualization/geometry";
import type { RunVisualization, TrackPath } from "@/types/api";

const SELECTED_COLOR = "var(--color-accent)";
const MUTED_COLOR = "var(--color-foreground-faint)";

interface TrackPathVisualizationProps {
  readonly visualization: RunVisualization;
  /** 'null' draws every track; a track id draws only that one. */
  readonly selectedTrackId: number | null;
  readonly onSelectTrack: (trackId: number) => void;
}

export function TrackPathVisualization({
  visualization,
  selectedTrackId,
  onSelectTrack,
}: TrackPathVisualizationProps) {
  const extent = useMemo(() => frameExtent(visualization), [visualization]);
  const visible = useMemo(
    () => selectVisible(visualization.paths, selectedTrackId),
    [visualization.paths, selectedTrackId],
  );

  const label =
    selectedTrackId === null
      ? `Track paths in source-video pixel space. ${visualization.paths.length} tracks, ${visualization.observation_count} observations.`
      : `Track ${selectedTrackId} path in source-video pixel space, ${visible[0]?.observation_count ?? 0} observations.`;

  return (
    <FrameSurface extent={extent} label={label}>
      {visible.map((path) => (
        <TrackLine
          key={path.track_id}
          path={path}
          selected={selectedTrackId === path.track_id}
          emphasized={selectedTrackId !== null}
          onSelect={onSelectTrack}
        />
      ))}
    </FrameSurface>
  );
}

function selectVisible(paths: readonly TrackPath[], selectedTrackId: number | null): TrackPath[] {
  if (selectedTrackId === null) return [...paths];
  return paths.filter((path) => path.track_id === selectedTrackId);
}

function TrackLine({
  path,
  selected,
  emphasized,
  onSelect,
}: {
  readonly path: TrackPath;
  readonly selected: boolean;
  readonly emphasized: boolean;
  readonly onSelect: (trackId: number) => void;
}) {
  const first = path.points[0];
  const last = path.points[path.points.length - 1];
  const colour = selected || !emphasized ? SELECTED_COLOR : MUTED_COLOR;

  return (
    <g
      className="viz-track"
      data-selected={selected}
      role="button"
      tabIndex={0}
      aria-label={`Track ${path.track_id}, ${path.observation_count} observations`}
      onClick={() => onSelect(path.track_id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(path.track_id);
        }
      }}
    >
      <path
        d={pathData(path.points)}
        fill="none"
        stroke={colour}
        strokeWidth={selected ? 3 : 1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
        opacity={selected || !emphasized ? 0.95 : 0.4}
      />
      {first ? (
        <circle
          cx={first.x}
          cy={first.y}
          r={3}
          fill="none"
          stroke={colour}
          strokeWidth={1.5}
          vectorEffect="non-scaling-stroke"
        />
      ) : null}
      {last ? <circle cx={last.x} cy={last.y} r={3} fill={colour} /> : null}
    </g>
  );
}
