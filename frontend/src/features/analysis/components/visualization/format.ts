import type { MetricValue, TrackMetrics } from "@/types/api";

const UNIT_LABELS: Record<string, string> = {
  count: "",
  seconds: "s",
  pixels: "px",
  pixels_per_second: "px/s",
  pixels_per_second_squared: "px/s²",
};

export function formatMetricValue(metric: MetricValue | undefined): string {
  if (!metric) return "—";
  if (metric.availability === "unavailable" || metric.value === null) return "Unavailable";
  return `${formatNumber(metric.value)}${suffix(metric.unit)}`;
}

export function metricOf(track: TrackMetrics, name: MetricValue["name"]): MetricValue | undefined {
  return track.metrics.find((metric) => metric.name === name);
}

export function formatNumber(value: number): string {
  if (Number.isInteger(value)) return value.toLocaleString();
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function formatSeconds(value: number): string {
  const minutes = Math.floor(value / 60);
  const seconds = value - minutes * 60;
  const rendered = seconds.toFixed(seconds < 10 ? 1 : 0).padStart(minutes > 0 ? 4 : 1, "0");
  return minutes > 0 ? `${minutes}:${rendered}` : `${rendered}s`;
}

function suffix(unit: string): string {
  const label = UNIT_LABELS[unit];
  return label ? ` ${label}` : "";
}
