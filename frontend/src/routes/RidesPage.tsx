import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSessionStore } from "../state/sessionStore";
import { cgApi, type SessionListItem } from "../lib/cgApi";
import { isDemoMode } from "../demo/demoMode";
import { demoRides } from "../demo/demoRides";

// CANARY (module load)
console.log("RIDES DEBUG MODULE LOADED v1");

type SessionsListResponse = { value: any[]; Count?: number; rows?: any[] } | any[];

const fmtNum = (n?: number | null, digits = 0): string =>
  typeof n === "number" && Number.isFinite(n) ? n.toFixed(digits) : "—";

// PATCH FINAL #1: robust precision watt getter (SSOT + fallback for legacy nested metrics)
const getPrecisionWattAvg = (row: any): number | null => {
  const v1 = row?.precision_watt_avg;
  if (typeof v1 === "number" && Number.isFinite(v1)) return v1;

  const v2 = row?.metrics?.precision_watt_avg;
  if (typeof v2 === "number" && Number.isFinite(v2)) return v2;

  const v3 = row?.metrics?.precision_watt_pedal;
  if (typeof v3 === "number" && Number.isFinite(v3)) return v3;

  return null;
};

// Coerce numeric strings helper
const coerceNum = (v: any): number | null => {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
};

const fmtMmSs = (sec: number | null | undefined): string => {
  if (typeof sec !== "number" || !Number.isFinite(sec) || sec <= 0) return "—";
  const s = Math.round(sec);
  const hh = Math.floor(s / 3600);
  const mm = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  if (hh > 0) return `${hh}:${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
  return `${mm}:${String(ss).padStart(2, "0")}`;
};

const fmtHr = (v: any): string => {
  if (typeof v !== "number" || !Number.isFinite(v) || v <= 0) return "—";
  return String(Math.round(v));
};

const getDistanceKm = (row: any): number | null => {
  const raw =
    row?.distance_km ??
    row?.metrics?.distance_km ??
    row?.distanceKm ??
    row?.distance;
  const v = coerceNum(raw);
  if (v != null && v > 0) return v;
  return null;
};

const getElapsedS = (row: any): number | null => {
  const raw =
    row?.elapsed_s ??
    row?.metrics?.elapsed_s ??
    row?.elapsed ??
    row?.elapsedSec ??
    row?.moving_time_s;
  const v = coerceNum(raw);
  if (v != null && v > 0) return v;
  return null;
};

const getHrAvg = (row: any): number | null => {
  const raw = row?.hr_avg ?? row?.metrics?.hr_avg;
  const v = coerceNum(raw);
  if (v != null && v > 0) return v;
  return null;
};

const getHrMax = (row: any): number | null => {
  const raw = row?.hr_max ?? row?.metrics?.hr_max;
  const v = coerceNum(raw);
  if (v != null && v > 0) return v;
  return null;
};

// NEW: Elevation gain getter
const getElevationGain = (row: any): number | null => {
  const raw =
    row?.elevation_gain_m ??
    row?.metrics?.elevation_gain_m ??
    row?.total_elevation_gain ??
    row?.elevationGain;
  const v = coerceNum(raw);
  if (v != null && v >= 0) return v;
  return null;
};

// NEW: Average speed calculated from distance + elapsed, or from field
// Average speed: prefer moving_s (excludes pauses) over elapsed_s
const getMovingS = (row: any): number | null => {
  const raw = row?.moving_s ?? row?.metrics?.moving_s;
  const v = coerceNum(raw);
  if (v != null && v > 0) return v;
  return null;
};
const getAvgSpeedKmh = (row: any): number | null => {
  const direct =
    row?.avg_speed_kmh ??
    row?.metrics?.avg_speed_kmh ??
    row?.average_speed_kmh;
  const dv = coerceNum(direct);
  if (dv != null && dv > 0) return dv;
  const dist = getDistanceKm(row);
  const seconds = getElapsedS(row);  // Use elapsed for now, moving_s is unreliable
  if (dist != null && seconds != null && seconds > 0) {
    const hours = seconds / 3600;
    const speed = dist / hours;
    if (speed > 0 && speed < 150) return speed;
  }
  return null;
};

// Robust time parsing
function toMillis(v: any): number | null {
  if (v == null) return null;

  if (typeof v === "number" && Number.isFinite(v)) {
    return v < 1e11 ? Math.round(v * 1000) : Math.round(v);
  }

  if (typeof v === "string") {
    const t = Date.parse(v);
    if (Number.isFinite(t)) return t;

    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v);
    if (m) {
      const y = Number(m[1]);
      const mo = Number(m[2]) - 1;
      const d = Number(m[3]);
      return new Date(y, mo, d, 12, 0, 0).getTime();
    }

    const asNum = Number(v);
    if (Number.isFinite(asNum)) return toMillis(asNum);
  }

  return null;
}

function parseTime(v?: string | number | null): number {
  const t = toMillis(v);
  return t == null ? -1 : t;
}

function isEra5(src?: string | null): boolean {
  const s = (src ?? "").toLowerCase();
  return s.includes("era5");
}

function weatherBadge(
  src?: string | null
): { label: string; tone: "good" | "warn" | "neutral" } {
  const s = (src ?? "").trim();
  if (!s) return { label: "unknown", tone: "neutral" };
  if (isEra5(s)) return { label: "ERA5", tone: "good" };
  if (s.toLowerCase().includes("neutral")) return { label: "neutral", tone: "warn" };
  return { label: s, tone: "neutral" };
}

function minutesBetween(start?: string | number | null, end?: string | number | null): number | null {
  const a = toMillis(start);
  const b = toMillis(end);
  if (a == null || b == null) return null;
  const mins = Math.round((b - a) / 60000);
  return mins >= 0 ? mins : null;
}

function formatStartDateTime(start?: string | number | null): string {
  const t = toMillis(start);
  if (t == null) return "Unknown";
  return new Date(t).toLocaleString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatEndTime(end?: string | number | null): string | null {
  const t = toMillis(end);
  if (t == null) return null;
  return new Date(t).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

const Badge: React.FC<{ tone: "good" | "warn" | "neutral"; children: React.ReactNode }> = ({
  tone,
  children,
}) => {
  const cls =
    tone === "good"
      ? "border-emerald-300 bg-gradient-to-r from-emerald-50 to-emerald-100 text-emerald-800 font-bold"
      : tone === "warn"
      ? "border-amber-300 bg-gradient-to-r from-amber-50 to-amber-100 text-amber-800 font-bold"
      : "border-slate-300 bg-gradient-to-r from-slate-50 to-slate-100 text-slate-700 font-medium";

  return (
    <span
      className={`inline-flex items-center rounded-full border-2 px-3 py-1 text-xs shadow-sm ${cls}`}
    >
      {children}
    </span>
  );
};

// Metric stat box used in ride card
const StatBox: React.FC<{
  icon: string;
  label: string;
  value: string;
  highlight?: boolean;
}> = ({ icon, label, value, highlight = false }) => (
  <div className="flex flex-col gap-0.5 min-w-0">
    <span className="text-xs font-medium text-slate-500 whitespace-nowrap">
      {icon} {label}
    </span>
    <span
      className={`text-base font-black tabular-nums whitespace-nowrap ${
        highlight ? "text-indigo-600" : "text-slate-900"
      }`}
    >
      {value}
    </span>
  </div>
);

// -------------------------------
// DEMO PAGE
// -------------------------------
const DemoRidesPage: React.FC = () => {
  console.log("RIDES DEBUG COMPONENT RENDER v1");
  (window as any).__CG_RIDES_CANARY = "rides-demo-canary";

  useEffect(() => {
    (window as any).__cg_rides_rows = demoRides ?? [];
  }, []);

  const rows = useMemo(() => {
    return [...demoRides].sort((a, b) => b.date.localeCompare(a.date));
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50/30 px-4 py-8">
      <div className="mx-auto max-w-5xl">
        <section className="mb-8">
          <h1 className="text-4xl font-black tracking-tight text-slate-900 mb-3">Your Rides</h1>
          <p className="text-lg text-slate-600 font-medium max-w-2xl">
            Demo view of your rides (hardcoded data). Showing {rows.length} session(s).
          </p>
          <div className="mt-3 inline-flex items-center gap-2 rounded-full border-2 border-indigo-200 bg-gradient-to-r from-indigo-50 to-purple-50 px-4 py-1.5 shadow-sm">
            <span className="text-xs font-bold text-indigo-700">
              Source: <span className="font-mono">demoRides.ts</span>
            </span>
          </div>
        </section>

        <section className="space-y-4">
          {rows.map((r) => {
            const durationMin = r.duration > 0 ? Math.round(r.duration / 60) : 0;
            const km = r.distance > 0 ? r.distance / 1000 : 0;

            return (
              <Link
                key={String(r.id)}
                to={`/session/${r.id}`}
                className="group block w-full rounded-2xl border-2 border-slate-200 bg-white p-6 shadow-lg transition-all duration-300 hover:-translate-y-1 hover:border-indigo-300 hover:shadow-xl focus:outline-none focus:ring-4 focus:ring-indigo-100"
                aria-label={`Open ride ${r.name}`}
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0 space-y-2">
                    <div className="text-xl font-black text-slate-900 truncate">{r.name}</div>
                    <div className="flex flex-wrap items-center gap-3 text-sm">
                      <span className="text-slate-600 font-medium">
                        📅 {new Date(`${r.date}T12:00:00`).toLocaleDateString("en-GB")}
                      </span>
                      <span className="text-slate-400">•</span>
                      <span className="capitalize text-indigo-600 font-bold">
                        {r.rideType.replace("-", " ")}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-4 text-base">
                      <span className="text-slate-700 font-semibold">🚴 {km.toFixed(1)} km</span>
                      <span className="text-slate-400">•</span>
                      <span className="text-slate-700 font-semibold">⏱️ {durationMin} min</span>
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-row items-center justify-between gap-4 sm:flex-col sm:items-end sm:justify-start">
                    <div className="text-3xl font-black text-indigo-600 leading-none tracking-tight">
                      {Math.round(r.precisionWatt)} W
                    </div>
                    <div className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-indigo-50 to-purple-50 border-2 border-indigo-200 px-4 py-2 text-xs font-bold text-indigo-700 shadow-sm">
                      <span className="text-base">⚡</span> Precision
                    </div>
                  </div>
                </div>
                <div className="mt-4 flex items-center gap-2 text-sm font-bold text-indigo-600 opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                  <span>Open ride details</span>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </Link>
            );
          })}
        </section>
      </div>
    </div>
  );
};

// -------------------------------
// REAL PAGE
// -------------------------------
const RealRidesPage: React.FC = () => {
  console.log("RIDES DEBUG COMPONENT RENDER v1");
  (window as any).__CG_RIDES_CANARY = "rides-real-canary";

  const navigate = useNavigate();
  const { sessionsList, loadingList, errorList, loadSessionsList } = useSessionStore();

  const [uiProfileVersion, setUiProfileVersion] = useState<string>("");
  const [showDev, setShowDev] = useState<boolean>(false);

  const lastReloadKeyRef = useRef<string>("");
  const didInitRef = useRef<boolean>(false);

  const normalizeSessionsList = (data: SessionsListResponse): any[] => {
    if (Array.isArray(data)) return data;
    const d: any = data as any;
    if (Array.isArray(d?.value)) return d.value;
    if (Array.isArray(d?.rows)) return d.rows;
    return [];
  };

  useEffect(() => {
    loadSessionsList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function refreshProfileVersion() {
      try {
        const p = await cgApi.profileGet().catch(() => null);
        const rec = p as unknown as Record<string, unknown> | null;
        const pv = String((rec?.profile_version as string | undefined) ?? "");
        if (!cancelled) setUiProfileVersion(pv);
      } catch {
        if (!cancelled) setUiProfileVersion("");
      }
    }

    void refreshProfileVersion();

    const onVis = () => {
      if (document.visibilityState === "visible") void refreshProfileVersion();
    };

    document.addEventListener("visibilitychange", onVis);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  useEffect(() => {
    const pv = uiProfileVersion.trim();
    if (!pv) return;

    if (!didInitRef.current) {
      didInitRef.current = true;
      lastReloadKeyRef.current = `pv::${pv}`;
      return;
    }

    const key = `pv::${pv}`;
    if (lastReloadKeyRef.current === key) return;

    lastReloadKeyRef.current = key;

    console.log("[RidesPage] profile_version changed → reloading list", { pv });
    loadSessionsList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uiProfileVersion]);

  const rows = useMemo(() => {
    const rawAny = (sessionsList ?? []) as any;
    const raw = Array.isArray(rawAny) ? rawAny : normalizeSessionsList(rawAny);
    const typed = (raw ?? []) as SessionListItem[];

    return [...typed].sort(
      (a, b) => parseTime((b as any).start_time ?? null) - parseTime((a as any).start_time ?? null)
    );
  }, [sessionsList]);

  useEffect(() => {
    (window as any).__cg_rides_rows = rows ?? [];
  }, [rows]);

  useEffect(() => {
    console.log("RIDES rows len", (rows as any)?.length ?? 0);
    console.log("RIDES sample keys", (rows as any)?.[0] ? Object.keys(rows[0] as any) : null);
  }, [rows]);

  if (loadingList) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50/30 px-4 py-8">
        <div className="mx-auto max-w-5xl">
          <div className="rounded-2xl border-2 border-indigo-200 bg-white p-6 text-center shadow-lg">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-indigo-600 border-r-transparent"></div>
            <p className="mt-4 text-lg font-bold text-slate-700">Loading rides…</p>
          </div>
        </div>
      </div>
    );
  }

  if (errorList) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50/30 px-4 py-8">
        <div className="mx-auto max-w-5xl space-y-4">
          <div className="rounded-2xl border-2 border-red-300 bg-gradient-to-br from-red-50 to-red-100 p-6 shadow-lg">
            <p className="text-base font-bold text-red-800">{errorList}</p>
          </div>
          <button
            type="button"
            onClick={() => loadSessionsList()}
            className="inline-flex items-center gap-2 rounded-xl border-2 border-slate-200 bg-white px-6 py-3 text-base font-bold text-slate-700 shadow-md transition-all duration-200 hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-lg"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50/30 px-4 py-8">
      <div className="mx-auto max-w-5xl">

        {/* Header */}
        <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-2">
            <h1 className="text-4xl font-black tracking-tight text-slate-900">Rides</h1>
            <p className="text-lg text-slate-600 font-medium">Showing {rows.length} session(s)</p>

            <div className="flex flex-wrap items-center gap-3">
              <span className="inline-flex items-center gap-2 rounded-full border-2 border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 shadow-sm">
                UI profile_version:{" "}
                <span className="font-mono font-bold">{uiProfileVersion || "n/a"}</span>
              </span>
              <button
                type="button"
                onClick={() => setShowDev((v) => !v)}
                className="text-xs font-bold text-indigo-600 underline hover:text-indigo-700"
              >
                {showDev ? "Hide DEV" : "Show DEV"}
              </button>
            </div>
          </div>

          <button
            type="button"
            onClick={() => loadSessionsList()}
            className="inline-flex items-center gap-2 rounded-xl border-2 border-slate-200 bg-white px-5 py-3 text-sm font-bold text-slate-700 shadow-md transition-all duration-200 hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-lg"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            Refresh
          </button>
        </header>

        {rows.length === 0 ? (
          <div className="rounded-2xl border-2 border-slate-200 bg-white p-8 text-center shadow-lg">
            <p className="text-lg font-medium text-slate-600">No rides found.</p>
          </div>
        ) : (
          <div className="space-y-5">
            {rows.map((s) => {
              const sid = String((s as any).session_id ?? (s as any).ride_id ?? "");
              const wx = weatherBadge((s as any).weather_source ?? null);

              const open = () => navigate(`/session/${sid}`, { state: { from: "rides" } });

              const mins = minutesBetween((s as any).start_time ?? null, (s as any).end_time ?? null);
              const startTxt = formatStartDateTime((s as any).start_time ?? null);
              const endTxt = formatEndTime((s as any).end_time ?? null);
              const timeRange =
                endTxt && mins != null
                  ? `${startTxt} – ${endTxt} (${mins} min)`
                  : startTxt;

              const distKm = getDistanceKm(s);
              const elapsedS = getElapsedS(s);
              const hrAvg = getHrAvg(s);
              const hrMax = getHrMax(s);
              const elevGain = getElevationGain(s);
              const avgSpeed = getAvgSpeedKmh(s);

              const durTxt =
                elapsedS != null ? fmtMmSs(elapsedS) : mins != null ? `${mins} min` : "—";
              const hrTxt =
                hrAvg != null || hrMax != null
                  ? `${hrAvg != null ? fmtHr(hrAvg) : "—"} / ${hrMax != null ? fmtHr(hrMax) : "—"}`
                  : "—";

              const pw = getPrecisionWattAvg(s);

              return (
                <div
                  key={String((s as any).session_id ?? (s as any).ride_id ?? "")}
                  role="button"
                  tabIndex={0}
                  onClick={open}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") open();
                  }}
                  className="group rounded-2xl border-2 border-slate-200 bg-white px-7 py-6 shadow-lg transition-all duration-300 hover:-translate-y-1 hover:border-indigo-300 hover:shadow-xl cursor-pointer"
                >
                  <div className="flex items-start justify-between gap-6">
                    <div className="min-w-0 flex-1 space-y-4">

                      {/* Headline row: time + badges */}
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="text-base font-black text-slate-900">{timeRange}</span>
                        <Badge tone={wx.tone}>Weather: {wx.label}</Badge>
                        <Badge tone="neutral">
                          Profile: {(s as any).profile_label ?? "unknown"}
                        </Badge>
                      </div>

                      {/* Stats grid — 3 cols on sm, wraps on mobile */}
                      <div className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-3 lg:grid-cols-6">
                        <StatBox
                          icon="🚴"
                          label="Distance"
                          value={distKm != null ? `${distKm.toFixed(1)} km` : "—"}
                        />
                        <StatBox
                          icon="⏱️"
                          label="Duration"
                          value={durTxt}
                        />
                        <StatBox
                          icon="💨"
                          label="Avg Speed"
                          value={avgSpeed != null ? `${avgSpeed.toFixed(1)} km/h` : "—"}
                        />
                        <StatBox
                          icon="⛰️"
                          label="Elevation"
                          value={elevGain != null ? `${Math.round(elevGain)} m` : "—"}
                        />
                        <StatBox
                          icon="❤️"
                          label="HR avg/max"
                          value={hrTxt}
                        />
                        <StatBox
                          icon="⚡"
                          label="Precision Watt"
                          value={pw !== null ? `${pw.toFixed(0)} W` : "—"}
                          highlight
                        />
                      </div>

                    </div>

                    {/* CTA */}
                    <div className="flex flex-col items-end gap-3 shrink-0">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          open();
                        }}
                        className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-5 py-3 text-sm font-black text-white shadow-md transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg"
                      >
                        Open
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M9 5l7 7-7 7"
                          />
                        </svg>
                      </button>
                      <div className="text-xs text-slate-400 font-medium group-hover:text-slate-600 transition-colors">
                        ID: <span className="font-mono font-bold">{sid}</span>
                      </div>
                    </div>
                  </div>

                  {/* DEV details (hidden by default) */}
                  {showDev && (
                    <div className="mt-4 rounded-xl border-2 border-slate-200 bg-slate-50 p-4 text-xs space-y-1 font-mono text-slate-600">
                      <div><span className="font-bold">session_id:</span> {sid}</div>
                      <div><span className="font-bold">ride_id:</span> {String((s as any).ride_id ?? "")}</div>
                      <div><span className="font-bold">weather_source:</span> {String((s as any).weather_source ?? "")}</div>
                      <div><span className="font-bold">start_time:</span> {String((s as any).start_time ?? "")}</div>
                      <div><span className="font-bold">end_time:</span> {String((s as any).end_time ?? "")}</div>
                      <div><span className="font-bold">elapsed_s:</span> {elapsedS == null ? "—" : String(elapsedS)}</div>
                      <div><span className="font-bold">distance_km:</span> {distKm == null ? "—" : String(distKm)}</div>
                      <div><span className="font-bold">elevation_gain_m:</span> {elevGain == null ? "—" : String(elevGain)}</div>
                      <div><span className="font-bold">avg_speed_kmh:</span> {avgSpeed == null ? "—" : avgSpeed.toFixed(1)}</div>
                      <div><span className="font-bold">hr_avg/hr_max:</span> {hrAvg == null ? "—" : fmtHr(hrAvg)}/{hrMax == null ? "—" : fmtHr(hrMax)}</div>
                      <div><span className="font-bold">precision_watt_avg:</span> {pw === null ? "null" : String(pw)}</div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

const RidesPage: React.FC = () => {
  console.log("RIDES DEBUG COMPONENT RENDER v1");
  return isDemoMode() ? <DemoRidesPage /> : <RealRidesPage />;
};

export default RidesPage;
