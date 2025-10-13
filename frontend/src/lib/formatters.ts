// frontend/src/lib/formatters.ts

type Opts = { fallback?: string };
const Fallback = "—";

function pickFallback(opts?: Opts) {
  return opts?.fallback ?? Fallback;
}

function isNum(x: unknown): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

function nf(
  locales: string,
  options?: Intl.NumberFormatOptions,
): Intl.NumberFormat {
  return new Intl.NumberFormat(locales, options);
}

const dec2 = nf("nb-NO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const dec1 = nf("nb-NO", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const int0 = nf("nb-NO", { maximumFractionDigits: 0 });
const pct1 = nf("nb-NO", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

/** Normalized Power, e.g. "206 W" */
export function formatNP(value: number | null | undefined, opts?: Opts): string {
  if (!isNum(value)) return pickFallback(opts);
  return `${int0.format(Math.round(value))} W`;
}

/** Intensity Factor (ratio), e.g. "0,65" (nb-NO uses comma) */
export function formatIF(value: number | null | undefined, opts?: Opts): string {
  if (!isNum(value)) return pickFallback(opts);
  return dec2.format(value);
}

/** Variability Index, e.g. "1,02" */
export function formatVI(value: number | null | undefined, opts?: Opts): string {
  if (!isNum(value)) return pickFallback(opts);
  return dec2.format(value);
}

/** Pa:Hr (% drift), e.g. "1,0 %" or "−0,5 %" */
export function formatPaHr(
  value: number | null | undefined,
  opts?: Opts,
): string {
  if (!isNum(value)) return pickFallback(opts);
  // Input forventes som prosentpoeng (f.eks. 1.0 betyr 1.0%)
  return pct1.format(value / 100);
}

/** W/slag (watts per beat), e.g. "1,30 W/slag" */
export function formatWattsPerBeat(
  value: number | null | undefined,
  opts?: Opts,
): string {
  if (!isNum(value)) return pickFallback(opts);
  return `${dec2.format(value)} W/slag`;
}

/** CGS (CycleGraph Score), e.g. "40,0" */
export function formatCGS(
  value: number | null | undefined,
  opts?: Opts,
): string {
  if (!isNum(value)) return pickFallback(opts);
  return dec1.format(value);
}

/* ────────────────────────────────────────────────────────────────────────────
 * Nye formattere for Sprint 11 (tid, tooltip, CI)
 * ────────────────────────────────────────────────────────────────────────────
 */

export type DataSource = "mock" | "api";

/**
 * Konverterer sekunder → hh:mm:ss (eller mm:ss hvis < 1 time).
 *  - 0  → "00:00"
 *  - 75 → "01:15"
 *  - 3661 → "01:01:01"
 */
export function formatTime(
  seconds: number | null | undefined,
  opts?: Opts,
): string {
  if (!isNum(seconds)) return pickFallback(opts);
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  const hh = h.toString().padStart(2, "0");
  const mm = m.toString().padStart(2, "0");
  const s2 = ss.toString().padStart(2, "0");
  return h > 0 ? `${hh}:${mm}:${s2}` : `${mm}:${s2}`;
}

/**
 * Tooltip-header som matcher badge-logikken.
 * Eksempel:
 *  - source="api", calibrated=true   → "Kilde: API – Kalibrert: Ja"
 *  - source="mock", calibrated=false → "Kilde: Mock – Kalibrert: Nei"
 */
export function formatTooltip(source: DataSource, calibrated: boolean): string {
  const src = source === "api" ? "API" : "Mock";
  const cal = calibrated ? "Ja" : "Nei";
  return `Kilde: ${src} – Kalibrert: ${cal}`;
}

/**
 * CI-tekst fra nedre/øvre konfidensbånd.
 * Viser "±X watt" hvor X = (upper - lower) / 2, avrundet til nærmeste heltall.
 * Returnerer "Mangler" hvis verdier er ugyldige eller mangler.
 */
export function formatCI(
  lower?: number | null,
  upper?: number | null,
): string {
  const hasLower = isNum(lower);
  const hasUpper = isNum(upper);
  if (!hasLower || !hasUpper) return "Mangler";

  let lo = lower as number;
  let hi = upper as number;
  if (hi < lo) {
    const tmp = hi;
    hi = lo;
    lo = tmp;
  }
  const half = (hi - lo) / 2;
  if (!Number.isFinite(half) || half < 0) return "Mangler";
  const x = Math.round(half);
  return `±${int0.format(x)} watt`;
}
