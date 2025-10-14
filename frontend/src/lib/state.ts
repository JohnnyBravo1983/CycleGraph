// frontend/src/lib/state.ts
// Hjelpefunksjoner for visningslogikk i kalibreringsflyt.

export type SeriesLike = {
  watts?: number[] | null;
  hr?: number[] | null;
};

export type SessionLike = {
  type?: "outdoor" | "indoor" | string | null;
  calibrated?: boolean | null;
  flags?: { hr_only?: boolean | null } | null;
  meta?: { calibrated?: boolean | null; is_first_outdoor?: boolean | null } | null;
  context?: { first_outdoor?: boolean | null } | null;
  labels?: string[] | null;
  series?: SeriesLike | null;
};

/**
 * Leser kalibreringsstatus fra mulige felter.
 */
function readCalibrated(session: SessionLike): boolean | null {
  if (typeof session?.calibrated === "boolean") return session.calibrated;
  if (typeof session?.meta?.calibrated === "boolean") return session.meta.calibrated!;
  return null;
}

/**
 * Leser flagg for "første outdoor-økt".
 */
function readIsFirstOutdoor(session: SessionLike): boolean {
  if (session?.meta?.is_first_outdoor) return true;
  if (session?.context?.first_outdoor) return true;
  if (Array.isArray(session?.labels) && session.labels.includes("first_outdoor")) return true;
  return false;
}

/**
 * Returnerer true hvis type=outdoor (case-insensitive).
 */
function readIsOutdoor(session: SessionLike): boolean {
  return (session?.type ?? "").toLowerCase() === "outdoor";
}

/**
 * Returnerer true hvis det kun finnes HR-data (ikke watt).
 */
function readHROnly(session: SessionLike): boolean {
  if (session?.flags?.hr_only === true) return true;
  const wattsLen = session?.series?.watts?.length ?? 0;
  const hrLen = session?.series?.hr?.length ?? 0;
  return hrLen > 0 && wattsLen === 0;
}

/**
 * True hvis dette er første outdoor-økt.
 */
export function isFirstOutdoorSession(session: SessionLike): boolean {
  return readIsOutdoor(session) && readIsFirstOutdoor(session);
}

/**
 * True hvis økten er HR-only (ingen watt).
 */
export function isHROnly(session: SessionLike): boolean {
  return readHROnly(session);
}

/**
 * True hvis modal for kalibrering skal vises.
 *  - vises kun for første outdoor-økter
 *  - ikke hvis allerede kalibrert
 *  - ikke hvis HR-only
 */
export function shouldShowCalibrationModal(session: SessionLike): boolean {
  const calibrated = readCalibrated(session);
  return isFirstOutdoorSession(session) && calibrated !== true && !isHROnly(session);
}

/**
 * Returnerer visningsstatus ("Kalibrert", "Ikke kalibrert", "Ukjent").
 * Bruker formatters.formatCalibrationStatus for konsistent tekst.
 */
import { formatCalibrationStatus } from "./formatters";

export function getCalibrationLabel(session: SessionLike): string {
  return formatCalibrationStatus(readCalibrated(session));
}
