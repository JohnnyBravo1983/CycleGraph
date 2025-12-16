import type { SessionReport } from "../types/session";

export function metric(
  s: SessionReport | null | undefined,
  key: "precision_watt" | "drag_watt" | "rolling_watt" | "total_watt"
): number {
  const v =
    (s as any)?.metrics?.[key] ??
    (s as any)?.[key] ??
    (s as any)?.metrics?.[key + "_avg"]; // bare i tilfelle eldre navn
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
}
