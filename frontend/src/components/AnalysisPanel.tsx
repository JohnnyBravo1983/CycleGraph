// frontend/src/components/AnalysisPanel.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import AnalysisChart from "./AnalysisChart";

type CIShape = { lower?: number[]; upper?: number[] };

export type PanelSeries = {
  t: number[];
  watts?: number[];
  hr?: number[];
  precision_watt_ci?: CIShape;
  // meta for visning
  source?: "API" | "Mock" | string;
  calibrated?: boolean; // kan mangle i eldre schema
  status?: "FULL" | "HR-only" | "LIMITED" | string;

  // Trinn 4: profilverdier brukt i analysen
  profile_cda?: number | null;
  profile_crr?: number | null;
  profile_crank_efficiency?: number | null;
  profile_version?: number | null;
};

export interface AnalysisPanelProps {
  series: PanelSeries;
  /** TRINN 6: valgfri override fra forelderen (SessionView). Hvis ikke satt, leses fra ENV. */
  useLiveTrends?: boolean;
}

/** TRINN 6: Les toggle fra Vite-ENV (string/boolean) */
function readUseLiveTrends(): boolean {
  const env = (import.meta as unknown as { env: Record<string, unknown> }).env;
  const v = env?.VITE_USE_LIVE_TRENDS;
  return v === true || v === "true";
}

function Badge({ kind }: { kind: "FULL" | "HR-only" | "LIMITED" | string }) {
  const map: Record<string, string> = {
    FULL: "bg-emerald-100 text-emerald-800 border-emerald-200",
    "HR-only": "bg-amber-100 text-amber-900 border-amber-200",
    LIMITED: "bg-slate-100 text-slate-800 border-slate-200",
  };
  const cls = map[kind] ?? "bg-slate-100 text-slate-800 border-slate-200";
  return (
    <span className={`inline-flex items-center gap-1 rounded-xl border px-2 py-0.5 text-xs ${cls}`}>
      {kind}
    </span>
  );
}

function prettySource(v: string): string {
  const lower = v.toLowerCase();
  if (lower === "api") return "API";
  if (lower === "mock") return "Mock";
  return v.charAt(0).toUpperCase() + v.slice(1).toLowerCase();
}

/** Liten farget prikk for legend-status */
function StatusDot({ state }: { state: "yes" | "no" | "unknown" }) {
  const color =
    state === "yes" ? "bg-emerald-500" : state === "no" ? "bg-rose-500" : "bg-slate-300";
  const label =
    state === "yes" ? "Kalibrert" : state === "no" ? "Ikke kalibrert" : "Kalibreringsstatus ukjent";
  return (
    <span
      aria-label={label}
      data-testid="calibration-status-dot"
      className={`inline-block h-2.5 w-2.5 rounded-full ${color}`}
    />
  );
}

/** Chip m/tekst og tooltip for kalibrering */
function CalibrationBadge({
  calibrated,
  hrOnly,
}: {
  calibrated: boolean | undefined;
  hrOnly?: boolean;
}) {
  // Ved HR-only skal vi vise "—" og grå prikk + enkel forklaring
  if (hrOnly) {
    const tooltip =
      "Denne økten har bare pulsdata (ingen wattmåler). Kalibrering er ikke aktuelt.";
    return (
      <span
        title={tooltip}
        aria-label={tooltip}
        data-testid="calibration-badge"
        className="inline-flex items-center gap-2 px-2 py-0.5 rounded-md text-xs text-slate-700 bg-slate-50 ring-1 ring-slate-200"
      >
        <StatusDot state="unknown" />
        Kalibrert: –
      </span>
    );
  }

  const state: "yes" | "no" | "unknown" =
    calibrated === true ? "yes" : calibrated === false ? "no" : "unknown";

  const text =
    state === "yes" ? "Kalibrert: Ja" : state === "no" ? "Kalibrert: Nei" : "Kalibrert: –";

  const tooltip =
    state === "yes"
      ? "Økten er kalibrert. Målingene tar hensyn til CdA og Crr."
      : state === "no"
      ? "Denne økten er ikke kalibrert. Kalibrering gir mer presise målinger av luft- og rullemotstand."
      : "Kalibreringsstatus er ukjent for denne økten.";

  const chipClass =
    state === "yes"
      ? "text-emerald-700 bg-emerald-50 ring-1 ring-emerald-200"
      : state === "no"
      ? "text-rose-700 bg-rose-50 ring-1 ring-rose-200"
      : "text-slate-700 bg-slate-50 ring-1 ring-slate-200";

  return (
    <span
      title={tooltip}
      aria-label={tooltip}
      data-testid="calibration-badge"
      className={`inline-flex items-center gap-2 px-2 py-0.5 rounded-md text-xs ${chipClass}`}
    >
      <StatusDot state={state} />
      {text}
    </span>
  );
}

export default function AnalysisPanel({ series, useLiveTrends: useLiveTrendsProp }: AnalysisPanelProps) {
  const [showPower, setShowPower] = useState(true);
  const [showHR, setShowHR] = useState(true);
  const [showPWCI, setShowPWCI] = useState(true);

  // TRINN 6: bestem modus (prop vinner over ENV)
  const useLiveTrends = useLiveTrendsProp ?? readUseLiveTrends();

  // QA-logg ved mount (ikke spam)
  const qaLoggedRef = useRef(false);
  useEffect(() => {
    if (qaLoggedRef.current) return;
    qaLoggedRef.current = true;
 
    console.log(useLiveTrends ? "TrendsChart bruker LIVE-data" : "TrendsChart bruker MOCK-data");
  }, [useLiveTrends]);

  const n = useMemo(() => series.t?.length ?? 0, [series.t]);
  const hasPower = (series.watts?.length ?? 0) > 0;
  const hasHR = (series.hr?.length ?? 0) > 0;
  const hasCI =
    !!series.precision_watt_ci &&
    ((series.precision_watt_ci.lower?.length ?? 0) > 0 ||
      (series.precision_watt_ci.upper?.length ?? 0) > 0);

  const canTogglePower = hasPower;
  const canToggleHR = hasHR;
  const canToggleCI = hasCI;

  const sourceRaw = typeof series.source === "string" ? series.source : (useLiveTrends ? "API" : "Mock");
  const sourceLabel = useMemo(() => prettySource(sourceRaw), [sourceRaw]);

  // Behold tri-state (true/false/undefined) for riktig tooltip/visning
  const calibratedTri = series.calibrated;
  const status =
    (series.status as string) ??
    (hasPower && hasHR ? "FULL" : hasHR ? "HR-only" : "LIMITED");

  // Ny: eksplisitt HR-only flagg
  const hrOnly = status === "HR-only" || (hasHR && !hasPower);

  return (
    <div
      className="rounded-2xl border border-slate-200 bg-white shadow-sm"
      data-testid="analysis-panel"
      data-live-trends={useLiveTrends ? "1" : "0"}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-slate-800">Analyse</h2>
          <span className="text-xs text-slate-500">Status</span>
          <Badge kind={status} />
          <span className="text-xs text-slate-500">samples: {n}</span>
        </div>

        {/* Legend / meta (kilde + kalibrering) */}
        <div className="flex items-center gap-3 text-xs text-slate-600" role="group" aria-label="Legend">
          <span
            className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5"
            data-testid="panel-source"
            title={`Kilde: ${sourceLabel}`}
            aria-label={`Kilde: ${sourceLabel}`}
          >
            {sourceLabel}
          </span>

          {/* HR-only: tving '—' og grå indikator */}
          <CalibrationBadge calibrated={calibratedTri} hrOnly={hrOnly} />
        </div>
      </div>

      <div className="flex items-center justify-between px-4 pt-3">
        <div className="flex items-center gap-2">
          <label
            className={`text-xs inline-flex items-center gap-1 px-2 py-1 rounded-lg border ${
              canTogglePower ? "cursor-pointer border-slate-300" : "opacity-50 border-slate-200"
            }`}
          >
            <input
              type="checkbox"
              className="accent-slate-700"
              checked={showPower}
              onChange={(e) => setShowPower(e.target.checked)}
              disabled={!canTogglePower}
            />
            Power
          </label>

          <label
            className={`text-xs inline-flex items-center gap-1 px-2 py-1 rounded-lg border ${
              canToggleHR ? "cursor-pointer border-slate-300" : "opacity-50 border-slate-200"
            }`}
          >
            <input
              type="checkbox"
              className="accent-slate-700"
              checked={showHR}
              onChange={(e) => setShowHR(e.target.checked)}
              disabled={!canToggleHR}
            />
            HR
          </label>

          <label
            className={`text-xs inline-flex items-center gap-1 px-2 py-1 rounded-lg border ${
              canToggleCI ? "cursor-pointer border-slate-300" : "opacity-50 border-slate-200"
            }`}
          >
            <input
              type="checkbox"
              className="accent-slate-700"
              checked={showPWCI}
              onChange={(e) => setShowPWCI(e.target.checked)}
              disabled={!canToggleCI}
            />
            CI-bånd (PW)
            <span className="ml-1 opacity-70">{hasCI ? "Tilgjengelig" : "Mangler"}</span>
          </label>
        </div>
      </div>

      {/* Trinn 4: profilverdier brukt i denne analysen */}
      <div className="px-4 pt-2 pb-1 text-xs text-slate-600">
        <div className="flex flex-wrap gap-4">
          {series.profile_cda != null && (
            <div>
              <span className="font-medium">CdA</span>{" "}
              <span className="font-mono">{series.profile_cda.toFixed(3)}</span>
            </div>
          )}
          {series.profile_crr != null && (
            <div>
              <span className="font-medium">Crr</span>{" "}
              <span className="font-mono">{series.profile_crr.toFixed(4)}</span>
            </div>
          )}
          {series.profile_crank_efficiency != null && (
            <div>
              <span className="font-medium">Crank efficiency</span>{" "}
              <span className="font-mono">
                {(series.profile_crank_efficiency * 100).toFixed(1)} %
              </span>{" "}
              <span className="text-[0.65rem] uppercase tracking-wide text-slate-500">
                locked
              </span>
            </div>
          )}
          {series.profile_version != null && (
            <div>
              <span className="font-medium">Profilversjon</span>{" "}
              <span className="font-mono">{series.profile_version}</span>
            </div>
          )}
        </div>
      </div>

      {/* Chart */}
      <div className="p-4">
        <div data-testid="analysis-chart-in-panel">
          <AnalysisChart
            series={series}
            showPower={showPower}
            showHR={showHR}
            showPWCI={showPWCI}
          />
        </div>
      </div>
    </div>
  );
}