import type { ReactNode } from "react";

import type { FrameExtent } from "@/features/analysis/components/visualization/geometry";

interface FrameSurfaceProps {
  readonly extent: FrameExtent;
  readonly label: string;
  readonly children: ReactNode;
}

// The source-frame backdrop every visualization draws on.
export function FrameSurface({ extent, label, children }: FrameSurfaceProps) {
  const viewBox = `${extent.left} ${extent.top} ${extent.width} ${extent.height}`;

  return (
    <svg
      className="viz-frame-surface"
      viewBox={viewBox}
      role="img"
      aria-label={label}
      preserveAspectRatio="xMidYMid meet"
      // The surface's box follows the source-frame aspect ratio, so the drawn
      // area is never stretched and the page never scrolls sideways on a phone.
      style={{ aspectRatio: `${extent.width} / ${extent.height}` }}
    >
      <rect
        x={extent.left}
        y={extent.top}
        width={extent.width}
        height={extent.height}
        className="viz-frame-backdrop"
      />
      {children}
    </svg>
  );
}
