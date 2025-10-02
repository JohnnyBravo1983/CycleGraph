// frontend/src/components/SessionCard.tsx
import type { SessionReport } from "../types/session";
import {
  formatNP,
  formatIF,
  formatVI,
  formatPaHr,
  formatWattsPerBeat,
  formatCGS,
} from "../lib/formatters";

/** Lokal utvidelse for S9: vi trenger calibration_reason i UI uten å endre types-filen nå */
type SessionWithCalib = SessionReport & {
  calibration_reason?: string | null;
};

type Props = {
  session: SessionWithCalib;
  className?: string;
};

/** Heuristikk for short-session guard:
 * - eksplisitt reason === "short_session"
 * - eller <30 samples hvis watts/precision_watt er arrays
 */
function isShortSession(s: SessionReport): boolean {
  if (s.reason === "short_session") return true;
  const wLen = Array.isArray(s.watts) ? s.watts.length : Infinity;
  const pwLen = Array.isArray(s.precision_watt) ? s.precision_watt.length : Infinity;
  const minLen = Math.min(wLen, pwLen);
  return minLen < 30;
}

/** Enkel deteksjon av no-power (brukes for varselbanner) */
function isNoPower(s: SessionReport): boolean {
  if (s.watts === null) return true;
  if (Array.isArray(s.watts) && s.watts.length === 0) return true;
  return false;
}

function CalibBadge({ ok }: { ok: boolean }) {
  const base =
    "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold";
  const tone = ok
    ? "bg-emerald-100 text-emerald-800"
    : "bg-amber-100 text-amber-800";
  return <span className={`${base} ${tone}`}>{ok ? "Kalibrert: Ja" : "Kalibrert: Nei"}</span>;
}

function InfoChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full bg-slate-100 text-slate-800 px-2 py-0.5 text-xs font-medium">
      {children}
    </span>
  );
}

/** Indoor/Outdoor-badge (primærchip) */
function IoBadge({ mode }: { mode?: "indoor" | "outdoor" }) {
  if (!mode) return null; // bakoverkomp: vises ikke hvis feltet mangler
  const tone =
    mode === "indoor"
      ? "bg-violet-100 text-violet-800"
      : "bg-sky-100 text-sky-800";
  const label = mode === "indoor" ? "Indoor" : "Outdoor";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${tone}`}>
      {label}
    </span>
  );
}

/** PrecisionWatt: vises direkte nå, men med fallback "—" */
function displayPrecisionWatt(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${Math.round(v)} W`;
}

export default function SessionCard({ session, className }: Props) {
  const shortGuard = isShortSession(session);
  const noPower = isNoPower(session);
  const calibReason = session.calibration_reason ?? null;

  return (
    <div className={`rounded-2xl border border-slate-200 bg-white shadow-sm ${className ?? ""}`}>
      <div className="p-4 sm:p-5">
        {/* Topp-rad: Chips (uten ModeBadge) */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            {/* Primær: Indoor/Outdoor */}
            <IoBadge mode={session.mode} />
            {/* Kalibrert */}
            <CalibBadge ok={session.calibrated} />
            {/* Optional: enkel status-chip */}
            {session.status ? <InfoChip>status: {session.status}</InfoChip> : null}
          </div>
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
          {noPower && (
            <div className="rounded-lg border border-sky-200 bg-sky-50 p-3 text-sm text-sky-800">
              Ingen watt-data i økten. (PW/NP/IF/VI/CGS kan være utilgjengelige.)
            </div>
          )}
        </div>

        {/* Metrikk-grid */}
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {/* NB: formatNP inkluderer "W" */}
          <Metric label="NP" value={formatNP(session.np)} />
          <Metric label="IF" value={formatIF(session.if_)} />
          <Metric label="VI" value={formatVI(session.vi)} />
          <Metric label="Pa:Hr" value={formatPaHr(session.pa_hr)} />
          {/* NB: formatWattsPerBeat inkluderer "W/slag" */}
          <Metric label="W/slag" value={formatWattsPerBeat(session.w_per_beat)} />
          <Metric label="CGS" value={formatCGS(session.cgs)} />
          {/* PrecisionWatt (direkte, ingen formatter nå) */}
          <Metric label="PrecisionWatt" value={displayPrecisionWatt(session.precision_watt_value)} />
        </div>

        {/* Bunn-info (valgfritt) */}
        <div className="mt-4 text-xs text-slate-500">
          Kilde: {session.sources?.join(", ") || "—"}
        </div>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-xl border border-slate-100 p-3">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-900">{value}</div>
    </div>
  );
}
