/**
 * series.ts
 * Downsampling/decimation for 1 Hz tidsserier (Power/HR) + enkle statistikker.
 * Trend helpers – CSV → grafserier
 *
 * Hovedfunksjoner:
 *  - decimateSeries(data, maxPoints): number[]
 *      Bruker LTTB (Largest-Triangle-Three-Buckets) for å bevare form/peaks når vi
 *      går fra ~7200 pkt → f.eks. 500–1000 pkt. Returnerer verdier i ny rekkefølge.
 *
 *  - getSeriesStats(data): { min, max, avg }
 *      Raske statistikker for tooltip/akser/CI.
 *
 *  - Trend helpers for CSV → grafserier
 *      mapSummaryCsvToSeries, mapPivotCsvToSeries, mapCsvToSeries
 *
 * Ekstra (anbefalt ved multi-serie):
 *  - lttbIndices(y, maxPoints): number[]
 *      Returnerer valgte INDEKSER (inkl. første & siste). Bruk samme indekser på
 *      t[], watts[], hr[] for konsistent decimation i x og y.
 *
 * Ytelse:
 *  - LTTB-implementasjonen er O(n) og allokerer små hjelpe-arrays. For n≈7.2k og
 *    maxPoints≈1000 er dette svært raskt og trygt i render-løkker.
 *
 * Edge-cases:
 *  - Non-finite (NaN/±Inf) erstattes med sist kjente gyldige verdi (fallback 0).
 *  - Hvis data.length <= maxPoints → returnerer kopi av data (ingen endring).
 */

// ─────────────────────────────────────────────────────────────
// Trend types – CSV → grafserier
// ─────────────────────────────────────────────────────────────

/**
 * Generisk punkt brukt i TrendsChart.
 * x:
 *  - summary.csv  → Date (ISO-dato fra "date"-kolonnen)
 *  - pivot.csv    → string (f.eks. "open_meteo" / "frozen")
 * y:
 *  - alltid en numerisk verdi (avg_watt, w_per_beat eller mean)
 */
export type TrendPoint = {
  x: Date | string;
  y: number;
};

// ─────────────────────────────────────────────────────────────
// Series statistics and downsampling
// ─────────────────────────────────────────────────────────────

export function getSeriesStats(data: number[]): { min: number; max: number; avg: number } {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  let sum = 0;
  let count = 0;

  let lastValid = 0;
  let hasLast = false;

  for (let i = 0; i < data.length; i++) {
    let v = data[i];
    if (!Number.isFinite(v)) {
      if (hasLast) v = lastValid;
      else v = 0;
    }
    // registrer som gyldig nå
    lastValid = v;
    hasLast = true;

    if (v < min) min = v;
    if (v > max) max = v;
    sum += v;
    count++;
  }

  if (count === 0) return { min: NaN, max: NaN, avg: NaN };
  return { min, max, avg: sum / count };
}

/**
 * LTTB (Largest-Triangle-Three-Buckets) – velger indekser som bevarer formen.
 * @param y råverdier (y = data[i]), x antas lik i (1 Hz, jevnt samplet)
 * @param maxPoints ønsket antall punkter totalt (inkl. første og siste)
 * @returns valgte indekser, alltid sortert stigende og inkl. 0 og n-1 når n>0
 */
export function lttbIndices(y: number[], maxPoints: number): number[] {
  const n = y.length;
  if (maxPoints >= n || n <= 2) {
    // returner alle indekser
    const idx = new Array<number>(n);
    for (let i = 0; i < n; i++) idx[i] = i;
    return idx;
  }

  // Pre-normaliser non-finite → "hold" forrige gyldige verdi (fallback 0 i start)
  const prep = new Array<number>(n);
  let last = 0;
  let hasLast = false;
  for (let i = 0; i < n; i++) {
    const v = y[i];
    if (Number.isFinite(v)) {
      last = v;
      hasLast = true;
      prep[i] = v;
    } else {
      prep[i] = hasLast ? last : 0;
    }
  }

  const bucketCount = maxPoints - 2; // mellom første og siste
  const every = (n - 2) / bucketCount;

  const out = new Array<number>(maxPoints);
  let outPos = 0;
  out[outPos++] = 0; // start

  let a = 0; // index til sist valgte punkt
  for (let b = 0; b < bucketCount; b++) {
    const rangeStart = Math.floor((b + 0) * every) + 1;
    const rangeEnd = Math.floor((b + 1) * every) + 1;
    const rangeStartClamped = Math.max(1, rangeStart);
    const rangeEndClamped = Math.min(n - 1, Math.max(rangeStartClamped + 1, rangeEnd));

    // Forventet "senter" på neste bøtte – bruker gjennomsnitt der som referanse (punkt C)
    const nextStart = Math.floor((b + 1) * every) + 1;
    const nextEnd = Math.floor((b + 2) * every) + 1;
    const nextS = Math.max(1, Math.min(n - 1, nextStart));
    const nextE = Math.max(1, Math.min(n - 1, Math.max(nextS + 1, nextEnd)));

    let avgX = 0;
    let avgY = 0;
    const span = nextE - nextS;
    for (let i = nextS; i < nextE; i++) {
      avgX += i;
      avgY += prep[i];
    }
    if (span > 0) {
      avgX /= span;
      avgY /= span;
    } else {
      avgX = (nextS + nextE) / 2;
      avgY = prep[Math.min(nextS, n - 1)];
    }

    // Finn punkt i [rangeStartClamped, rangeEndClamped) som maksimerer trekantarealet
    let maxArea = -1;
    let maxIdx = rangeStartClamped;

    const ax = a;
    const ay = prep[a];

    for (let i = rangeStartClamped; i < rangeEndClamped; i++) {
      // areal via kryssprodukt /2, |(A→B x A→C)|:
      const area =
        Math.abs((ax - avgX) * (prep[i] - ay) - (ax - i) * (avgY - ay));
      if (area > maxArea) {
        maxArea = area;
        maxIdx = i;
      }
    }

    out[outPos++] = maxIdx;
    a = maxIdx;
  }

  out[outPos++] = n - 1; // slutt
  return out;
}

/**
 * Decimate verdier med LTTB; returnerer selve verdiene i ny rekkefølge.
 * NB: Hvis du også trenger tid (t) og andre serier (watts/hr), bruk lttbIndices()
 *     og plukk ut samme indekser for alle serier for konsistent x/y.
 */
export function decimateSeries(data: number[], maxPoints: number): number[] {
  const n = data.length;
  if (maxPoints >= n) return data.slice(); // ingen endring

  const idx = lttbIndices(data, maxPoints);
  const out = new Array<number>(idx.length);
  // non-finite håndteres implisitt i lttbIndices via "prep", men vi leser originalverdi:
  // dersom original er non-finite, faller tilbake til sist gyldige.
  let last = 0;
  let hasLast = false;
  for (let k = 0; k < idx.length; k++) {
    const v = data[idx[k]];
    if (Number.isFinite(v)) {
      out[k] = v as number;
      last = v as number;
      hasLast = true;
    } else {
      out[k] = hasLast ? last : 0;
    }
  }
  return out;
}

// ─────────────────────────────────────────────────────────────
// Trend helpers – CSV → grafserier
// ─────────────────────────────────────────────────────────────

/**
 * Hjelper: splitter header + data og håndterer tomme/ufullstendige CSV-er.
 */
function splitHeaderAndRows(rows: string[][]): {
  header: string[] | null;
  data: string[][];
} {
  if (!rows || rows.length === 0) {
    return { header: null, data: [] };
  }

  const [header, ...data] = rows;
  return {
    header: header ?? null,
    data: data ?? [],
  };
}

/**
 * Mapper trend/summary.csv → tidsserie.
 *
 * Forventet format (Tr9-locked):
 *   date,session_id,avg_watt,avg_hr,w_per_beat,cda_used,crr_used
 *
 * @param rows   CSV-rows inkl. header
 * @param metric "avg_watt" eller "w_per_beat"
 */
export function mapSummaryCsvToSeries(
  rows: string[][],
  metric: 'avg_watt' | 'w_per_beat',
): TrendPoint[] {
  const { header, data } = splitHeaderAndRows(rows);
  if (!header || data.length === 0) {
    return [];
  }

  const lower = header.map((h) => (h ?? '').toLowerCase().trim());
  const dateIdx = lower.indexOf('date');
  const valueIdx = lower.indexOf(metric);

  if (dateIdx === -1 || valueIdx === -1) {
    return [];
  }

  const points: TrendPoint[] = [];

  for (const row of data) {
    const dateStr = row[dateIdx];
    const valStr = row[valueIdx];

    if (!dateStr) continue;

    const d = new Date(dateStr);
    const v = Number(valStr);

    if (!Number.isFinite(v) || Number.isNaN(v)) continue;

    points.push({
      x: d,
      y: v,
    });
  }

  return points;
}

/**
 * Mapper trend/pivot/<metric>.csv → kategoriserie.
 *
 * Forventet format:
 *   weather_source,mean,std,count
 *
 * Vi bruker:
 *   x = weather_source (string)
 *   y = mean (number)
 */
export function mapPivotCsvToSeries(rows: string[][]): TrendPoint[] {
  const { header, data } = splitHeaderAndRows(rows);
  if (!header || data.length === 0) {
    return [];
  }

  const lower = header.map((h) => (h ?? '').toLowerCase().trim());
  const weatherIdx = lower.indexOf('weather_source');
  const meanIdx = lower.indexOf('mean');

  if (weatherIdx === -1 || meanIdx === -1) {
    return [];
  }

  const points: TrendPoint[] = [];

  for (const row of data) {
    const label = row[weatherIdx];
    const valStr = row[meanIdx];

    if (!label) continue;

    const v = Number(valStr);
    if (!Number.isFinite(v) || Number.isNaN(v)) continue;

    points.push({
      x: label,
      y: v,
    });
  }

  return points;
}

/**
 * Backwards-/fallback-helper som brukes dersom vi bare trenger
 * en enkel serie uten å bry oss om metrikkslaget.
 *
 * Default: bruker "avg_watt" på summary.csv.
 */
export function mapCsvToSeries(rows: string[][]): TrendPoint[] {
  return mapSummaryCsvToSeries(rows, 'avg_watt');
}