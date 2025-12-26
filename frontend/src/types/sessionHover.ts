import type { SessionListItem } from "./session";
import { formatStartTimeForUi } from "../lib/api";

/**
 * Hover-visning skal være lett, stabil og basert på sessions-lista.
 * "Truth" for watt her er precision_watt_avg fra SessionListItem.
 */
export type SessionHoverSummary = Pick<
  SessionListItem,
  | "session_id"
  | "ride_id"
  | "start_time"
  | "distance_km"
  | "precision_watt_avg"
  | "profile_label"
  | "weather_source"
>;

/** Små formattere – hold UI stabilt selv om backend mangler felter */
export function fmtWatt(w?: number | null): string {
  if (w === null || w === undefined) return "—";
  if (!Number.isFinite(w)) return "—";
  return `${Math.round(w)} W`;
}

export function fmtKm(km?: number | null): string {
  if (km === null || km === undefined) return "—";
  if (!Number.isFinite(km)) return "—";
  return `${km.toFixed(1)} km`;
}

export function fmtStartTime(start?: string | null): string {
  return formatStartTimeForUi(start ?? null);
}

export function fmtWeather(src?: string | null): string {
  if (!src) return "—";
  return src;
}

export function fmtProfile(label?: string | null): string {
  if (!label) return "—";
  return label;
}
