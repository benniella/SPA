"use client";

import { useMemo } from "react";

import { formatSeconds } from "@/features/analysis/components/visualization/format";
import type { ActivityTimeline as Timeline, RunVisualization } from "@/types/api";

interface ActivityTimelineProps {
  readonly visualization: RunVisualization;
  /** 'null' shows every track; a track id narrows the buckets to that track. */
  readonly selectedTrackId: number | null;
}

export function ActivityTimeline({ visualization, selectedTrackId }: ActivityTimelineProps) {
  const buckets = useMemo(
    () => narrowToTrack(visualization.timeline, selectedTrackId),
    [visualization.timeline, selectedTrackId],
  );
  const maxCount = useMemo(
    () => buckets.reduce((max, bucket) => Math.max(max, bucket.count), 0),
    [buckets],
  );

  if (buckets.length === 0) {
    return (
      <p className="text-caption">This run has no observations, so there is no activity to show.</p>
    );
  }

  return (
    <div className="stack stack-3">
      <ol className="viz-timeline" aria-label="Observation activity over the run">
        {buckets.map((bucket) => {
          const share = maxCount > 0 ? bucket.count / maxCount : 0;
          return (
            <li
              key={bucket.index}
              className="viz-timeline-bucket"
              aria-label={`${formatSeconds(bucket.start)} to ${formatSeconds(bucket.end)}: ${bucket.count} observations`}
            >
              <span
                className="viz-timeline-bar"
                style={{ height: `${Math.max(share * 100, bucket.count > 0 ? 6 : 0)}%` }}
                data-empty={bucket.count === 0}
                aria-hidden="true"
              />
            </li>
          );
        })}
      </ol>

      <div className="viz-timeline-axis">
        <span className="text-micro">{formatSeconds(buckets[0]?.start ?? 0)}</span>
        <span className="text-micro">{formatSeconds(buckets[buckets.length - 1]?.end ?? 0)}</span>
      </div>

      <p className="text-caption">
        Each bar is one {formatSeconds(visualization.timeline.bucket_seconds)} interval. Height is
        the number of tracked observations recorded in it.
      </p>
    </div>
  );
}

interface NarrowedBucket {
  readonly index: number;
  readonly start: number;
  readonly end: number;
  readonly count: number;
}

function narrowToTrack(timeline: Timeline, selectedTrackId: number | null): NarrowedBucket[] {
  return timeline.buckets.map((bucket) => ({
    index: bucket.index,
    start: bucket.start_seconds,
    end: bucket.end_seconds,
    count:
      selectedTrackId === null
        ? bucket.observation_count
        : bucket.track_ids.includes(selectedTrackId)
          ? bucket.observation_count
          : 0,
  }));
}
