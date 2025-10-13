import React, { useMemo, useCallback } from "react";
import AnalysisChart, { AnalysisSeries } from "./AnalysisChart";
import { lttbIndices } from "../lib/series";

/**
 * AnalysisPanel.tsx
 * Panel som pakker inn AnalysisChart + metadata i en responsiv layout.
 *
 * - Desktop: 2-kol grid (graf | metadata)
 * - Mobil: stacked
 * - Robust mot HR-only/LIMITED (manglende watts/CI skal ikke krasje)
 * - CI-bånd vises/skjules automatisk
 *
 * Props:
 *  - series: AnalysisSeries utgangspunkt (t, watts?, hr?, pw_ci_lower/upper?, source, calibrated)
 *  - status: "HR-only" | "LIMITED" | "FULL" | string
 *  - maxPoints: ønsket maks punkter (default 900)
 *
 * Merk om CI:
 *  - Panel støtter også alternative feltformer fra backend:
 *      precision_watt_ci: { lower: number[]; upper: number[] }  ELLER  [lower, upper]
 *    Disse mappes inn til pw_ci_lower/upper før decimation.
 */

type StatusKind = "HR-only" | "LIMITED" | "FULL" | string;

export interface AnalysisPanelProps {
  series: AnalysisSeries & {
    status?: StatusKind;
    precision_watt_ci?:
      | { lower?: number[]; upper?: number[] }
      | [number[] | undefined, number[] | undefined];
  };
  maxPoints?: number;
  className?: string;
  "data-testid"?: string;
}

function normalizeCI(
  s: AnalysisPanelProps["series"]
): { lower?: number[]; upper?: number[] } {
  if (Array.isArray(s.pw_ci_lower) && Array.isArray(s.pw_ci_upper)) {
    return { lower: s.pw_ci_lower, upper: s.pw_ci_upper };
  }
  const ci = s.precision_watt_ci;
  if (Array.isArray(ci)) {
    const lower = Array.isArray(ci[0]) ? ci[0] : undefined;
    const upper = Array.isArray(ci[1]) ? ci[1] : undefined;
    return { lower, upper };
  }
  if (ci && typeof ci === "object") {
    const lower = Array.isArray(ci.lower) ? ci.lower : undefined;
    const upper = Array.isArray(ci.upper) ? ci.upper : undefined;
    return { lower, upper };
  }
  return {};
}

function pickPrimaryY(series: AnalysisSeries): number[] | undefined {
  if (series.watts && series.watts.length) return series.watts;
  if (series.hr && series.hr.length) return series.hr;
  return undefined;
}

function sampleIndicesFallback(length: number, maxPoints: number): number[] {
  if (length <= maxPoints) {
    return Array.from({ length }, (_, i) => i);
  }
  const step = Math.ceil(length / maxPoints);
  const idx: number[] = [];
  for (let i = 0; i < length; i += step) idx.push(i);
  if (idx[idx.length - 1] !== length - 1) idx.push(length - 1);
  return idx;
}

export default function AnalysisPanel({
  series,
  maxPoints = 900,
  className = "",
  "data-testid": testId = "analysis-panel",
}: AnalysisPanelProps) {
  const { lower: ciLower, upper: ciUpper } = normalizeCI(series);
  const primary = pickPrimaryY(series);

  const indices = useMemo(() => {
    const n = series.t?.length ?? 0;
    if (!n) return [];
    if (primary && primary.length === n) {
      return lttbIndices(primary, maxPoints);
    }
    return sampleIndicesFallback(n, maxPoints);
  }, [series.t, primary, maxPoints]);

  // 🔧 Stabil avhengighet: bundet til indices
  const mapByIdx = useCallback(
    (arr?: number[]) =>
      arr && arr.length
        ? indices.map((i) => (Number.isFinite(arr[i]!) ? (arr[i] as number) : NaN))
        : undefined,
    [indices]
  );

  const decimated: AnalysisSeries = useMemo(() => {
    const tt = indices.map((i) => (Number.isFinite(series.t[i]!) ? (series.t[i] as number) : i));
    return {
      t: tt,
      watts: mapByIdx(series.watts),
      hr: mapByIdx(series.hr),
      pw_ci_lower: mapByIdx(ciLower),
      pw_ci_upper: mapByIdx(ciUpper),
      source: series.source,
      calibrated: series.calibrated,
    };
  }, [
    indices,
    series.t,
    series.watts,
    series.hr,
    ciLower,
    ciUpper,
    series.source,
    series.calibrated,
    mapByIdx, // ✅ lagt til for eslint-hooks
  ]);

  const hasPower = !!decimated.watts?.length;
  const hasHR = !!decimated.hr?.length;
  const hasCI = !!decimated.pw_ci_lower?.length && !!decimated.pw_ci_upper?.length;

  const status: StatusKind =
    (series.status as StatusKind) ??
    (hasPower && hasHR ? "FULL" : hasHR && !hasPower ? "HR-only" : "LIMITED");

  return (
    <section
      className={`w-full ${className}`}
      data-testid={testId}
      aria-label="Analysis panel"
    >
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-5">
        {/* Graf */}
        <div className="xl:col-span-4 rounded-2xl border border-slate-200 bg-white p-3">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700">Tidsserie (Power/HR)</h2>
            <div className="flex items-center gap-2 text-xs">
              <span
                className={`rounded-full px-2 py-0.5 ${
                  series.source === "api"
                    ? "bg-blue-100 text-blue-800"
                    : "bg-slate-100 text-slate-800"
                }`}
                title="Datakilde"
              >
                {series.source === "api" ? "API" : "Mock"}
              </span>
              <span
                className={`rounded-full px-2 py-0.5 ${
                  series.calibrated ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                }`}
                title="Kalibreringsstatus"
              >
                {series.calibrated ? "Kalibrert" : "Ikke kalibrert"}
              </span>
            </div>
          </div>

          <AnalysisChart
            data={decimated}
            showPower={hasPower}
            showHR={hasHR}
            showPWCI={hasCI}
            height={320}
            data-testid="analysis-chart-in-panel"
          />
        </div>

        {/* Metadata */}
        <aside className="xl:col-span-1 rounded-2xl border border-slate-200 bg-white p-3">
          <h3 className="mb-2 text-sm font-semibold text-slate-700">Metadata</h3>

          <dl className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <dt className="text-slate-500">Status</dt>
              <dd>
                <span
                  className={`rounded-full px-2 py-0.5 ${
                    status === "FULL"
                      ? "bg-emerald-100 text-emerald-800"
                      : status === "HR-only"
                      ? "bg-violet-100 text-violet-800"
                      : "bg-amber-100 text-amber-800"
                  }`}
                  title="Datadekning"
                >
                  {status}
                </span>
              </dd>
            </div>

            <div className="flex items-center justify-between">
              <dt className="text-slate-500">Kalibrert</dt>
              <dd className="font-medium">{series.calibrated ? "Ja" : "Nei"}</dd>
            </div>

            <div className="flex items-center justify-between">
              <dt className="text-slate-500">Kilde</dt>
              <dd className="font-medium">{series.source === "api" ? "API" : "Mock"}</dd>
            </div>

            <div className="flex items-center justify-between">
              <dt className="text-slate-500">CI-bånd (PW)</dt>
              <dd className="font-medium">{hasCI ? "Tilgjengelig" : "Mangler"}</dd>
            </div>
          </dl>

          {status === "HR-only" && (
            <p className="mt-3 text-xs leading-5 text-slate-500">
              Økten mangler wattdata. Grafen viser kun HR. CI-bånd for PrecisionWatt skjules automatisk.
            </p>
          )}
        </aside>
      </div>
    </section>
  );
}
