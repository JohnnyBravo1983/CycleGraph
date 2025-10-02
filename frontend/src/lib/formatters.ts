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
