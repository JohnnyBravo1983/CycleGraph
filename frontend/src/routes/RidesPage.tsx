// frontend/src/routes/RidesPage.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSessionStore } from "../state/sessionStore";
import { cgApi, type SessionListItem } from "../lib/cgApi";
import { isDemoMode } from "../demo/demoMode";
import { demoRides } from "../demo/demoRides";

type SessionsListResponse = { value: any[]; Count?: number; rows?: any[] } | any[];

const fmtNum = (n?: number | null, digits = 0): string =>
  typeof n === "number" && Number.isFinite(n) ? n.toFixed(digits) : "—";

const getPrecisionWattAvg = (row: any): number | null => {
  const v = row?.precision_watt_avg;
  return typeof v === "number" && Number.isFinite(v) ? v : null;
};

function parseTime(v?: string | null): number {
  if (!v) return -1;
  const t = Date.parse(v);
  if (Number.isFinite(t)) return t;

  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v);
  if (!m) return -1;
  const y = Number(m[1]);
  const mo = Number(m[2]) - 1;
  const d = Number(m[3]);
  return new Date(y, mo, d, 12, 0, 0).getTime();
}

function isEra5(src?: string | null): boolean {
  const s = (src ?? "").toLowerCase();
  return s.includes("era5");
}

function weatherBadge(
  src?: string | null
): { label: string; tone: "good" | "warn" | "neutral" } {
  const s = (src ?? "").trim();
  if (!s) return { label: "ukjent", tone: "neutral" };
  if (isEra5(s)) return { label: "ERA5", tone: "good" };
  if (s.toLowerCase().includes("neutral")) return { label: "neutral", tone: "warn" };
  return { label: s, tone: "neutral" };
}

function minutesBetween(start?: string | null, end?: string | null): number | null {
  if (!start || !end) return null;
  const a = Date.parse(start);
  const b = Date.parse(end);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
  const mins = Math.round((b - a) / 60000);
  return mins >= 0 ? mins : null;
}

function formatStartDateTime(start?: string | null): string {
  if (!start) return "Ukjent";
  const t = Date.parse(start);
  if (!Number.isFinite(t)) return "Ukjent";
  return new Date(t).toLocaleString("nb-NO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatEndTime(end?: string | null): string | null {
  if (!end) return null;
  const t = Date.parse(end);
  if (!Number.isFinite(t)) return null;
  return new Date(t).toLocaleTimeString("nb-NO", {
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

// -------------------------------
// DEMO PAGE
// -------------------------------
const DemoRidesPage: React.FC = () => {
  const rows = useMemo(() => {
    return [...demoRides].sort((a, b) => b.date.localeCompare(a.date));
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50/30 px-4 py-8">
      <div className="mx-auto max-w-5xl">
        {/* Header */}
        <section className="mb-8">
          <h1 className="text-4xl font-black tracking-tight text-slate-900 mb-3">Your Rides</h1>
          <p className="text-lg text-slate-600 font-medium max-w-2xl">
            Demo-visning av dine økter (hardcoded data). Viser {rows.length} økt(er).
          </p>
          <div className="mt-3 inline-flex items-center gap-2 rounded-full border-2 border-indigo-200 bg-gradient-to-r from-indigo-50 to-purple-50 px-4 py-1.5 shadow-sm">
            <span className="text-xs font-bold text-indigo-700">
              Kilde: <span className="font-mono">demoRides.ts</span>
            </span>
          </div>
        </section>

        {/* Rides List */}
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
                  {/* Left */}
                  <div className="min-w-0 space-y-2">
                    <div className="text-xl font-black text-slate-900 truncate">{r.name}</div>

                    <div className="flex flex-wrap items-center gap-3 text-sm">
                      <span className="text-slate-600 font-medium">
                        📅 {new Date(`${r.date}T12:00:00`).toLocaleDateString("nb-NO")}
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

                  {/* Right */}
                  <div className="flex shrink-0 flex-row items-center justify-between gap-4 sm:flex-col sm:items-end sm:justify-start">
                    <div className="text-3xl font-black text-indigo-600 leading-none tracking-tight">
                      {Math.round(r.precisionWatt)} W
                    </div>

                    <div
                      className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-indigo-50 to-purple-50 border-2 border-indigo-200 px-4 py-2 text-xs font-bold text-indigo-700 shadow-sm"
                      title="Precision Watt (beta) · Target accuracy ~3–5% in good conditions"
                    >
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
  const navigate = useNavigate();
  const { sessionsList, loadingList, errorList, loadSessionsList } = useSessionStore();

  const [uiProfileVersion, setUiProfileVersion] = useState<string>("");
  const [showDev, setShowDev] = useState<boolean>(false);

  const lastReloadKeyRef = useRef<string>("");
  const didInitRef = useRef<boolean>(false);

  // PATCH A — Normalize API response (array vs {value:[...]} etc) as a failsafe
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
      (a, b) => parseTime(b.start_time ?? null) - parseTime(a.start_time ?? null)
    );
  }, [sessionsList]);

  // DEBUG (temporary): verify rows shape + watt fields
  useEffect(() => {
    console.log("RIDES rows len", (rows as any)?.length ?? 0);
    console.log("RIDES sample keys", (rows as any)?.[0] ? Object.keys(rows[0] as any) : null);

    const want = new Set(["15378170998", "15412107820"]);
    const hits = (rows ?? []).filter((r: any) =>
      want.has(String(r?.session_id ?? r?.ride_id ?? ""))
    );
    console.log("RIDES hits", hits);
  }, [rows]);

  if (loadingList) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50/30 px-4 py-8">
        <div className="mx-auto max-w-5xl">
          <div className="rounded-2xl border-2 border-indigo-200 bg-white p-6 text-center shadow-lg">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-indigo-600 border-r-transparent"></div>
            <p className="mt-4 text-lg font-bold text-slate-700">Laster økter…</p>
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
            Prøv igjen
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
            <h1 className="text-4xl font-black tracking-tight text-slate-900">Økter</h1>
            <p className="text-lg text-slate-600 font-medium">Viser {rows.length} økt(er)</p>

            <div className="flex flex-wrap items-center gap-3">
              <span className="inline-flex items-center gap-2 rounded-full border-2 border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 shadow-sm">
                ui profile_version:{" "}
                <span className="font-mono font-bold">{uiProfileVersion || "n/a"}</span>
              </span>
              <button
                type="button"
                onClick={() => setShowDev((v) => !v)}
                className="text-xs font-bold text-indigo-600 underline hover:text-indigo-700"
              >
                {showDev ? "Skjul DEV" : "Vis DEV"}
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
            Oppdater
          </button>
        </header>

        {rows.length === 0 ? (
          <div className="rounded-2xl border-2 border-slate-200 bg-white p-8 text-center shadow-lg">
            <p className="text-lg font-medium text-slate-600">Ingen økter funnet.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {rows.map((s) => {
              const sid = String((s as any).session_id ?? (s as any).ride_id ?? "");
              const wx = weatherBadge((s as any).weather_source ?? null);

              const distOk =
                typeof (s as any).distance_km === "number" &&
                Number.isFinite((s as any).distance_km);

              const open = () => navigate(`/session/${sid}`, { state: { from: "rides" } });

              const mins = minutesBetween((s as any).start_time ?? null, (s as any).end_time ?? null);
              const startTxt = formatStartDateTime((s as any).start_time ?? null);
              const endTxt = formatEndTime((s as any).end_time ?? null);
              const timeRange = endTxt && mins != null ? `${startTxt} – ${endTxt} (${mins} min)` : startTxt;

              const kmTxt = distOk ? `${((s as any).distance_km as number).toFixed(1)} km` : "—";

              // SSOT: only read from row.precision_watt_avg
              const pw = getPrecisionWattAvg(s);

              return (
                <div
                  key={sid}
                  role="button"
                  tabIndex={0}
                  onClick={open}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") open();
                  }}
                  className="group rounded-2xl border-2 border-slate-200 bg-white p-6 shadow-lg transition-all duration-300 hover:-translate-y-1 hover:border-indigo-300 hover:shadow-xl cursor-pointer"
                >
                  <div className="flex items-start justify-between gap-6">
                    <div className="min-w-0 space-y-3">
                      {/* Headline */}
                      <div className="flex flex-wrap items-center gap-3">
                        <div className="text-base font-black text-slate-900">{timeRange}</div>
                        <Badge tone={wx.tone}>Vær: {wx.label}</Badge>
                        <Badge tone="neutral">Profil: {(s as any).profile_label ?? "ukjent"}</Badge>
                      </div>

                      {/* Metrics */}
                      <div className="flex flex-wrap gap-x-8 gap-y-2 text-base">
                        <div className="flex items-center gap-2">
                          <span className="text-slate-600 font-medium">🚴 Km:</span>
                          <span className="font-black text-slate-900">{kmTxt}</span>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="text-slate-600 font-medium">⚡ Precision Watt:</span>
                          <span className="font-black text-indigo-600">
                            {pw !== null ? `${pw.toFixed(0)} W` : "—"}
                          </span>
                        </div>
                      </div>

                      {/* DEV details */}
                      {showDev && (
                        <div className="mt-3 rounded-xl border-2 border-slate-200 bg-slate-50 p-4 text-xs space-y-1 font-mono text-slate-600">
                          <div>
                            <span className="font-bold">session_id:</span> {sid}
                          </div>
                          <div>
                            <span className="font-bold">ride_id:</span> {String((s as any).ride_id ?? "")}
                          </div>
                          <div>
                            <span className="font-bold">weather_source:</span>{" "}
                            {String((s as any).weather_source ?? "")}
                          </div>
                          <div>
                            <span className="font-bold">start_time:</span> {String((s as any).start_time ?? "")}
                          </div>
                          <div>
                            <span className="font-bold">end_time:</span> {String((s as any).end_time ?? "")}
                          </div>
                          <div>
                            <span className="font-bold">mins:</span> {mins == null ? "—" : String(mins)}
                          </div>
                          <div>
                            <span className="font-bold">precision_watt_avg:</span>{" "}
                            {pw === null ? "null" : String(pw)}
                          </div>
                        </div>
                      )}
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
                        Åpne
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                      <div className="text-xs text-slate-400 font-medium group-hover:text-slate-600 transition-colors">
                        ID: <span className="font-mono font-bold">{sid}</span>
                      </div>
                    </div>
                  </div>
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
  return isDemoMode() ? <DemoRidesPage /> : <RealRidesPage />;
};

export default RidesPage;
