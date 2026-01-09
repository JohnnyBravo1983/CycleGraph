// frontend/src/routes/RidesPage.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSessionStore } from "../state/sessionStore";
import { cgApi, type SessionListItem } from "../lib/cgApi";
import { isDemoMode } from "../demo/demoMode";
import { demoRides } from "../demo/demoRides";

const fmtNum = (n?: number | null, digits = 0): string =>
  typeof n === "number" && Number.isFinite(n) ? n.toFixed(digits) : "—";

function parseTime(v?: string | null): number {
  if (!v) return -1;
  const t = Date.parse(v);
  if (Number.isFinite(t)) return t;

  // fallback for YYYY-MM-DD (should parse fine, but be safe)
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

// ✅ PATCH: varighet i minutter
function minutesBetween(start?: string | null, end?: string | null): number | null {
  if (!start || !end) return null;
  const a = Date.parse(start);
  const b = Date.parse(end);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
  const mins = Math.round((b - a) / 60000);
  return mins >= 0 ? mins : null;
}

// ✅ PATCH: "Strava-ish" formatters
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
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : tone === "warn"
      ? "border-amber-200 bg-amber-50 text-amber-800"
      : "border-slate-200 bg-slate-50 text-slate-700";

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${cls}`}>
      {children}
    </span>
  );
};

// -------------------------------
// DEMO PAGE (uses demoRides SSOT)
// -------------------------------
const DemoRidesPage: React.FC = () => {
  // newest first
  const rows = useMemo(() => {
    return [...demoRides].sort((a, b) => b.date.localeCompare(a.date));
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight mb-2">Rides</h1>
        <p className="text-slate-600 max-w-xl">
          Demo-visning av dine økter (hardcoded data). Viser {rows.length} økt(er).
        </p>
        <div className="mt-2 text-xs text-slate-500">
          Kilde: <span className="font-mono">demoRides.ts</span>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        {rows.map((r) => {
          const durationMin = r.duration > 0 ? Math.round(r.duration / 60) : 0;
          const km = r.distance > 0 ? r.distance / 1000 : 0;

          return (
            <Link
              key={String(r.id)}
              to={`/session/${r.id}`}
              className={[
                "group w-full rounded-xl border border-slate-200 bg-white",
                "px-5 py-4 shadow-sm",
                "transition-all duration-200 ease-out",
                // ✅ PATCH B2: stronger hover shadow (Stripe/Linear-ish)
                "hover:-translate-y-0.5 hover:shadow-[0_4px_12px_rgba(0,0,0,0.12)] hover:border-emerald-400",
                "focus:outline-none focus:ring-2 focus:ring-emerald-200",
              ].join(" ")}
              aria-label={`Open ride ${r.name}`}
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                {/* Left */}
                <div className="min-w-0">
                  <div className="text-[16px] font-semibold text-slate-800 truncate">{r.name}</div>

                  <div className="mt-1 text-[14px] text-slate-500">
                    {new Date(`${r.date}T12:00:00`).toLocaleDateString("nb-NO")} ·{" "}
                    <span className="capitalize">{r.rideType.replace("-", " ")}</span>
                  </div>

                  <div className="mt-1 text-[14px] text-slate-500">
                    {km.toFixed(1)} km · {durationMin} min
                  </div>
                </div>

                {/* Right */}
                <div className="flex shrink-0 flex-row items-center justify-between gap-3 sm:flex-col sm:items-end sm:justify-start">
                  {/* ✅ PATCH B1: 22px + tracking-tight */}
                  <div className="text-[22px] font-bold text-emerald-500 leading-none tracking-tight">
                    {Math.round(r.precisionWatt)} W
                  </div>

                  {/* ✅ PATCH B3: title tooltip */}
                  <div
                    className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-1 text-[12px] font-medium text-emerald-600"
                    title="Precision Watt (beta) · Target accuracy ~3–5% in good conditions"
                  >
                    <span aria-hidden>⚡</span> Precision
                  </div>
                </div>
              </div>

              <div className="mt-3 text-[12px] text-slate-400 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                Open ride details →
              </div>
            </Link>
          );
        })}
      </section>
    </div>
  );
};

// -------------------------------
// REAL PAGE (unchanged)
// -------------------------------
const RealRidesPage: React.FC = () => {
  const navigate = useNavigate();
  const { sessionsList, loadingList, errorList, loadSessionsList } = useSessionStore();

  // Track ui profile_version + reload list når den endres
  const [uiProfileVersion, setUiProfileVersion] = useState<string>("");

  // DEV toggle (for console/debug)
  const [showDev, setShowDev] = useState<boolean>(false);

  // Guards
  const lastReloadKeyRef = useRef<string>("");
  const didInitRef = useRef<boolean>(false);

  // 1) Initial load
  useEffect(() => {
    loadSessionsList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 2) Refresh ui profile_version
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

  // 3) Når profile_version endrer seg -> reload sessions list
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
    const raw = (sessionsList ?? []) as SessionListItem[];
    // Sort newest first
    return [...raw].sort((a, b) => parseTime(b.start_time ?? null) - parseTime(a.start_time ?? null));
  }, [sessionsList]);

  if (loadingList) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6">
        <div className="text-sm text-slate-500">Laster økter…</div>
      </div>
    );
  }

  if (errorList) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-3">
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm">{errorList}</div>
        <button
          type="button"
          onClick={() => loadSessionsList()}
          className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-slate-50"
        >
          Prøv igjen
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-4">
      <header className="flex items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">Økter</h1>
          <p className="text-sm text-slate-500">Viser {rows.length} økt(er)</p>

          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs text-slate-400">
              ui profile_version: <span className="font-mono">{uiProfileVersion || "n/a"}</span>
            </span>
            <button
              type="button"
              onClick={() => setShowDev((v) => !v)}
              className="text-xs text-slate-500 underline hover:text-slate-700"
            >
              {showDev ? "Skjul DEV" : "Vis DEV"}
            </button>
          </div>
        </div>

        <button
          type="button"
          onClick={() => loadSessionsList()}
          className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-slate-50"
        >
          Oppdater
        </button>
      </header>

      {rows.length === 0 ? (
        <div className="rounded-lg border bg-white p-4 text-sm text-slate-500">Ingen økter funnet.</div>
      ) : (
        <div className="space-y-3">
          {rows.map((s) => {
            const sid = String(s.session_id ?? s.ride_id ?? "");
            const wx = weatherBadge(s.weather_source ?? null);

            const distOk = typeof s.distance_km === "number" && Number.isFinite(s.distance_km);
            const wattOk =
              typeof s.precision_watt_avg === "number" && Number.isFinite(s.precision_watt_avg);

            const open = () => navigate(`/session/${sid}`, { state: { from: "rides" } });

            // ✅ PATCH: time range + mins + km
            const mins = minutesBetween(s.start_time ?? null, (s as any).end_time ?? null);
            const startTxt = formatStartDateTime(s.start_time ?? null);
            const endTxt = formatEndTime((s as any).end_time ?? null);

            const timeRange =
              endTxt && mins != null ? `${startTxt} – ${endTxt} (${mins} min)` : startTxt;

            const kmTxt = distOk ? `${(s.distance_km as number).toFixed(1)} km` : "—";

            return (
              <div
                key={sid}
                role="button"
                tabIndex={0}
                onClick={open}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") open();
                }}
                className="group rounded-xl border bg-white p-4 hover:bg-slate-50/60 cursor-pointer"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 space-y-2">
                    {/* Headline */}
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-semibold text-slate-900">{timeRange}</div>

                      <Badge tone={wx.tone}>Vær: {wx.label}</Badge>
                      <Badge tone="neutral">Profil: {s.profile_label ?? "ukjent"}</Badge>
                    </div>

                    {/* Metrics */}
                    <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-700">
                      <div>
                        <span className="text-slate-500">Km:</span>{" "}
                        <span className="font-medium text-slate-900">{kmTxt}</span>
                      </div>

                      <div>
                        <span className="text-slate-500">Precision Watt:</span>{" "}
                        <span className="font-medium text-slate-900">
                          {wattOk ? `${fmtNum(s.precision_watt_avg, 0)} W` : "—"}
                        </span>
                      </div>
                    </div>

                    {/* DEV details */}
                    {showDev ? (
                      <div className="mt-2 rounded-md border bg-slate-50 p-2 text-xs text-slate-600">
                        <div>
                          <span className="text-slate-500">session_id:</span>{" "}
                          <span className="font-mono">{sid}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">ride_id:</span>{" "}
                          <span className="font-mono">{String(s.ride_id ?? "")}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">weather_source:</span>{" "}
                          <span className="font-mono">{String(s.weather_source ?? "")}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">start_time(raw):</span>{" "}
                          <span className="font-mono">{String(s.start_time ?? "")}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">end_time(raw):</span>{" "}
                          <span className="font-mono">{String((s as any).end_time ?? "")}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">mins:</span>{" "}
                          <span className="font-mono">{mins == null ? "—" : String(mins)}</span>
                        </div>
                      </div>
                    ) : null}
                  </div>

                  {/* CTA */}
                  <div className="flex flex-col items-end gap-2">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        open();
                      }}
                      className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-white"
                    >
                      Åpne →
                    </button>
                    <div className="text-xs text-slate-400 group-hover:text-slate-500">
                      ID: <span className="font-mono">{sid}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

const RidesPage: React.FC = () => {
  return isDemoMode() ? <DemoRidesPage /> : <RealRidesPage />;
};

export default RidesPage;
