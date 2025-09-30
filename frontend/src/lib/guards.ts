// frontend/src/lib/guards.ts
import type { SessionReport } from "../types/session";

/** Utvidet type som tillater et evt. fremtidig hr_series-felt */
type SessionLike = Partial<SessionReport> & {
  hr_series?: number[] | null;
};

function isNumberArray(v: unknown): v is number[] {
  return Array.isArray(v) && v.every((x) => typeof x === "number");
}

/**
 * Sjekker om økten er kort (< min samples)
 */
export function isShortSession(n: number, min = 30): boolean {
  return n < min;
}

/**
 * Prøver å gjette antall samples i en økt basert på tilgjengelige serier.
 * Rekkefølge:
 * 1. watts
 * 2. precision_watt
 * 3. hr_series (om tilstede)
 * 4. fallback = 0
 */
export function guessSampleLength(d: SessionLike): number {
  // watts kan være number | number[] | null | undefined
  if (isNumberArray(d.watts)) {
    return d.watts.length;
  }
  if (isNumberArray(d.precision_watt)) {
    return d.precision_watt.length;
  }
  if (isNumberArray(d.hr_series)) {
    return d.hr_series.length;
  }
  return 0;
}