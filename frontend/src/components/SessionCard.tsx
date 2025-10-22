import type { SessionReport } from "../types/session";
import type { ReactNode } from "react";
import {
  formatNP,
  formatIF,
  formatVI,
  formatPaHr,
  formatWattsPerBeat,
  formatCGS,
} from "../lib/formatters";

/** Lokale domene-typer for valgfri frontend-informasjon */
type PublishState = "pending" | "done" | "failed" | "skipped";
type Mode = "indoor" | "outdoor";

/** CI kan komme i flere varianter fra backend/persist */
type PrecisionCI = [number, number] | { low: number; high: number } | number | null | undefined;

/** Utvider SessionReport med felter som faktisk brukes i UI (alle valgfri) */
type SessionCore = SessionReport & {
  mode?: Mode;
  calibrated?: boolean;
  status?: string;

  // standard metrikker (kan være null/undefined i noen paths)
  np?: number | null;
  if_?: number | null;
  vi?: number | null;
  pa_hr?: number | null;
  w_per_beat?: number | null;
  cgs?: number | null;

  // PW felt fra ulike kilder
  precision_watt_value?: number | null;
  precision_watt?: number | number[] | null;

  // årsak / metadata
  reason?: string | null;
  sources?: string[];

  // rå strømmer
  watts: number[] | null;
};

type SessionWithCalib = SessionCore & {
  calibration_reason?: string | null;

  // Trinn 6 felter (alle valgfri – hentes fra session_metrics.*)
  publish_state?: PublishState;
  publish_time?: string; // ISO

  precision_watt_ci?: PrecisionCI;

  crr_used?: number;
  CdA?: number;

  rider_weight?: number;
  bike_weight?: number;
  tire_width?: number;
  bike_type?: string; // "road" | "tt" | ...
};

type Props = {
  session: SessionWithCalib;
  className?: string;
};

/** Heuristikk for short-session guard */
function isShortSession(s: SessionCore): boolean {
  const wLen = Array.isArray(s.watts) ? s.watts.length : Infinity;
  const pwLen = Array.isArray(s.precision_watt) ? s.precision_watt.length : Infinity;
  const minLen = Math.min(wLen, pwLen);
  if (s.reason === "short_session") return true;
  return minLen < 30;
}

/** Enkel deteksjon av no-power (brukes for varselbanner) */
function isNoPower(s: SessionCore): boolean {
  if (s.watts === null) return true;
  if (Array.isArray(s.watts) && s.watts.length === 0) return true;
  return false;
}

/** Type guards for CI-format */
function isCIArray(ci: PrecisionCI): ci is [number, number] {
  return Array.isArray(ci) && ci.length === 2 && ci.every((x) => typeof x === "number");
}
function isCIObject(ci: PrecisionCI): ci is { low: number; high: number } {
  return !!ci && typeof ci === "object" && !Array.isArray(ci) && "low" in ci && "high" in ci;
}

/** Normaliser CI til {low, high} (valgfri) */
function normalizeCI(ci: PrecisionCI): { low?: number; high?: number } {
  if (ci == null) return {};
  if (typeof ci === "number") return { low: ci, high: ci };
  if (isCIArray(ci)) return { low: ci[0], high: ci[1] };
  if (isCIObject(ci)) return { low: ci.low, high: ci.high };
  return {};
}

/** Publish-status-pill (inline for å unngå nye filer) */
function StatusPill({ state }: { state?: PublishState }) {
  const s: PublishState = state ?? "pending";
  const label: Record<PublishState, string> = {
    pending: "Pending",
    done: "Published",
    failed: "Failed",
    skipped: "Skipped",
  };
  const tone: Record<PublishState, string> = {
    pending: "bg-yellow-100 text-yellow-800 ring-yellow-200",
    done: "bg-emerald-100 text-emerald-800 ring-emerald-200",
    failed: "bg-red-100 text-red-800 ring-red-200",
    skipped: "bg-slate-100 text-slate-800 ring-slate-200",
  };
  const icon: Record<PublishState, string> = {
    pending: "⏳",
    done: "✓",
    failed: "⚠️",
    skipped: "⏭️",
  };
  return (
    <span
      data-testid="publish-pill"
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${tone[s]}`}
      title={`publish_state: ${s}`}
    >
      <span aria-hidden>{icon[s]}</span>
      {label[s]}
    </span>
  );
}

function CalibBadge({ ok }: { ok: boolean }) {
  const base =
    "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold";
  const tone = ok
    ? "bg-emerald-100 text-emerald-800"
    : "bg-amber-100 text-amber-800";
  return <span className={`${base} ${tone}`}>{ok ? "Kalibrert: Ja" : "Kalibrert: Nei"}</span>;
}

function InfoChip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full bg-slate-100 text-slate-800 px-2 py-0.5 text-xs font-medium">
      {children}
    </span>
  );
}

/** Indoor/Outdoor-badge (primærchip) */
function IoBadge({ mode }: { mode?: Mode }) {
  if (!mode) return null; // bakoverkomp: vises ikke hvis feltet mangler
  const tone =
    mode === "indoor" ? "bg-violet-100 text-violet-800" : "bg-sky-100 text-sky-800";
  const label = mode === "indoor" ? "Indoor" : "Outdoor";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${tone}`}>
      {label}
    </span>
  );
}

/** PW: støtter både session.precision_watt_value og ev. session.precision_watt */
function displayPrecisionWatt(session: SessionWithCalib): string {
  const raw =
    session.precision_watt_value ??
    (typeof session.precision_watt === "number" ? session.precision_watt : undefined);
  if (raw === null || raw === undefined || Number.isNaN(raw)) return "—";
  return `${Math.round(raw)} W`;
}

/** Formattering helpers */
function fmt(value: number | undefined | null, digits = 2, unit?: string): string {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  const num = value.toFixed(digits);
  return unit ? `${num} ${unit}` : num;
}

export default function SessionCard({ session, className }: Props) {
  const shortGuard = isShortSession(session);
  const noPower = isNoPower(session);
  const calibReason = session.calibration_reason ?? null;

  const ci = normalizeCI(session.precision_watt_ci);
  const reasonNote =
    session.reason === "indoor_session"
      ? "Rulleøkt – ikke kalibrert"
      : session.reason
      ? String(session.reason).split("_").join(" ")
      : null;

  return (
    <div className={`rounded-2xl border border-slate-200 bg-white shadow-sm ${className ?? ""}`}>
      <div className="p-4 sm:p-5">
        {/* Topp-rad: Chips + Publish-status */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            {/* Primær: Indoor/Outdoor */}
            <IoBadge mode={session.mode} />
            {/* Kalibrert */}
            <CalibBadge ok={Boolean(session.calibrated)} />
            {/* Optional: enkel status-chip (eksisterende) */}
            {session.status ? <InfoChip>status: {session.status}</InfoChip> : null}
          </div>

          {/* Ny: publish-state pill */}
          <StatusPill state={session.publish_state} />
        </div>

        {/* Varsler */}
        <div className="mt-3 space-y-2">
          {shortGuard && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              Kort økt: mindre enn 30 samples. Viser begrenset informasjon.
            </div>
          )}
          {!session.calibrated && calibReason && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              Ikke kalibrert: {calibReason}
            </div>
          )}
          {reasonNote && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              {reasonNote}
            </div>
          )}
          {noPower && (
            <div className="rounded-lg border border-sky-200 bg-sky-50 p-3 text-sm text-sky-800">
              Ingen watt-data i økten. (PW/NP/IF/VI/CGS kan være utilgjengelige.)
            </div>
          )}
        </div>

        {/* Metrikk-grid (eksisterende + nye felt for Trinn 6) */}
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {/* Eksisterende */}
          <Metric label="NP" value={formatNP(session.np)} />
          <Metric label="IF" value={formatIF(session.if_)} />
          <Metric label="VI" value={formatVI(session.vi)} />
          <Metric label="Pa:Hr" value={formatPaHr(session.pa_hr)} />
          <Metric label="W/slag" value={formatWattsPerBeat(session.w_per_beat)} />
          <Metric label="CGS" value={formatCGS(session.cgs)} />
          <Metric label="PrecisionWatt" value={displayPrecisionWatt(session)} />

          {/* Nytt: PrecisionWatt CI */}
          <Metric
            label="PW CI"
            value={
              ci.low !== undefined || ci.high !== undefined
                ? `${fmt(ci.low, 0)}–${fmt(ci.high, 0)} W`
                : "—"
            }
          />

          {/* Nytt: Aero & rulle */}
          <Metric label="CdA" value={fmt(session.CdA, 3, "m²")} />
          <Metric label="Crr" value={fmt(session.crr_used, 4)} />

          {/* Nytt: Sykkel & rytter */}
          <Metric label="Rytter" value={fmt(session.rider_weight, 0, "kg")} />
          <Metric label="Sykkel" value={fmt(session.bike_weight, 1, "kg")} />
          <Metric label="Dekkbredde" value={fmt(session.tire_width, 0, "mm")} />
          <Metric label="Type" value={session.bike_type ?? "—"} />

          {/* Nytt: Publish-tid (som egen “metric” for enkel layout) */}
          <Metric
            label="Publisert"
            value={session.publish_time ? new Date(session.publish_time).toLocaleString() : "—"}
          />
        </div>

        {/* Bunn-info (eksisterende) */}
        <div className="mt-4 text-xs text-slate-500">
          Kilde: {Array.isArray(session.sources) && session.sources.length > 0 ? session.sources.join(", ") : "—"}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-100 p-3">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-900">{value}</div>
    </div>
  );
}
