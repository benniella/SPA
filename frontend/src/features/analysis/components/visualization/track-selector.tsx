"use client";

import type { TrackPath } from "@/types/api";

interface TrackSelectorProps {
  readonly tracks: readonly TrackPath[];
  /** 'null' means every track is shown. */
  readonly selectedTrackId: number | null;
  readonly onSelect: (trackId: number | null) => void;
}

export function TrackSelector({ tracks, selectedTrackId, onSelect }: TrackSelectorProps) {
  return (
    <div className="viz-track-selector" role="group" aria-label="Track selection">
      <TrackOption
        label="All tracks"
        detail={`${tracks.length}`}
        selected={selectedTrackId === null}
        onSelect={() => onSelect(null)}
      />
      {tracks.map((track) => (
        <TrackOption
          key={track.track_id}
          label={`Track ${track.track_id}`}
          detail={track.observation_count.toLocaleString()}
          selected={selectedTrackId === track.track_id}
          onSelect={() => onSelect(track.track_id)}
        />
      ))}
    </div>
  );
}

function TrackOption({
  label,
  detail,
  selected,
  onSelect,
}: {
  readonly label: string;
  readonly detail: string;
  readonly selected: boolean;
  readonly onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className="viz-track-option"
      data-selected={selected}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className="viz-track-option-label">{label}</span>
      <span className="viz-track-option-detail">{detail}</span>
    </button>
  );
}
