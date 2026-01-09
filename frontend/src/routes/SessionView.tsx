// frontend/src/pages/SessionView.tsx
import React, { useEffect, useMemo, useRef } from "react";
import { useParams, Link, useLocation } from "react-router-dom";

import { useSessionStore } from "../state/sessionStore";
import type { SessionReport } from "../types/session";

import ErrorBanner from "../components/ErrorBanner";
import { ROUTES } from "../lib/routes";
import { cgApi } from "../lib/cgApi";

import { isDemoMode } from "../demo/demoMode";
import { demoRides } from "../demo/demoRides";

// ─────────────────────────────────────────────────────────────
// Helpers (tåler number og string med komma/punktum)
// ─────────────────────────────────────────────────────────────
function num(x: unknown): number | null {
  if (typeof x === "number") return Number.isFinite(x) ? x : null;
  if (typeof x === "string") {
    // tåler både "225.82" og "225,82"
    const s = x.trim().replace(",", ".");
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function fmtW(x: unknown): string {
  const n = num(x);
  return n === null ? "—" : `${n.toFixed(1)} W`;
}

function fmtKg(x: unknown): string {
  const n = num(x);
  return n === null ? "—" : `${n.toFixed(1)} kg`;
}

function fmtHpa(x: unknown): string {
  const n = num(x);
  return n === null ? "—" : `${n.toFixed(0)} hPa`;
}

function fmtMs(x: unknown): string {
  const n = num(x);
  return n === null ? "—" : `${n.toFixed(1)} m/s`;
}

function fmtC(x: unknown): string {
  const n = num(x);
  return n === null ? "—" : `${n.toFixed(1)} °C`;
}

// ─────────────────────────────────────────────────────────────
// Patch 3B helper: Metric card (used in DemoSessionView only)
// ─────────────────────────────────────────────────────────────
const Metric = ({ label, value }: { label: string; value: string }) => (
  <div className="border border-slate-200 rounded-lg p-4">
    <div className="text-[12px] uppercase tracking-wide text-slate-500">{label}</div>
    <div className="mt-1 text-[18px] font-semibold text-slate-800">{value}</div>
  </div>
);

// ─────────────────────────────────────────────────────────────
// PATCH 4C + 3B: Demo view (ingen backend-kall)
// ─────────────────────────────────────────────────────────────
const DemoSessionView: React.FC = () => {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";

  // Patch 3B.1: SSOT = demoRides
  const ride = useMemo(() => {
    return demoRides.find((r) => String((r as any).id) === String(id)) ?? null;
  }, [id]);

  if (!id) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Session</h1>
        <div className="rounded-xl border bg-white p-4 text-slate-700">Missing session id in URL.</div>
        <div className="flex gap-3">
          <Link to="/rides" className="px-4 py-2 rounded-xl border bg-white hover:bg-slate-50">
            ← Back to Rides
          </Link>
          <Link to="/dashboard" className="px-4 py-2 rounded-xl border bg-white hover:bg-slate-50">
            Dashboard
          </Link>
        </div>
      </div>
    );
  }

  if (!ride) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Session</h1>
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900">
          Could not find demo ride with ID <span className="font-mono">{id}</span>.
        </div>
        <div className="flex gap-3">
          <Link to="/rides" className="px-4 py-2 rounded-xl border bg-white hover:bg-slate-50">
            ← Back to Rides
          </Link>
          <Link to="/dashboard" className="px-4 py-2 rounded-xl border bg-white hover:bg-slate-50">
            Dashboard
          </Link>
        </div>
      </div>
    );
  }

  // Patch 3B.3: deterministisk “mock” power curve basert på rideType + duration
  const powerSeries = useMemo(() => {
    const minutes = Math.max(10, Math.round(((ride as any).duration ?? 0) / 60));
    const pw = Number((ride as any).precisionWatt ?? 0);

    const base =
      (ride as any).rideType === "long-ride"
        ? pw
        : pw * 1.1; // litt høyere base for kortere/hardere økter

    return Array.from({ length: minutes }, (_, i) => {
      const noise = Math.sin(i / 5) * 6;
      return Math.max(80, base + noise);
    });
  }, [ride]);

  // Safe access helpers (for demo data variability)
  const name = String((ride as any).name ?? "Ride");
  const date = String((ride as any).date ?? "");
  const rideType = String((ride as any).rideType ?? "ride").replace("-", " ");

  const distanceM = Number((ride as any).distance ?? 0);
  const durationS = Number((ride as any).duration ?? 0);
  const precisionWatt = Number((ride as any).precisionWatt ?? 0);

  const stravaWatt = Number((ride as any).stravaWatt ?? NaN);
  const elevation = Number((ride as any).elevation ?? NaN);
  const avgSpeed = Number((ride as any).avgSpeed ?? NaN);
  const riderWeight = Number((ride as any).riderWeight ?? NaN);

  const weather = ((ride as any).weather ?? null) as any;
  const tempVal = weather?.temp;
  const windSpeedVal = weather?.wind?.speed;
  const conditionsVal = weather?.conditions;

  return (
    <div className="flex flex-col gap-6">
      {/* Patch 3B.2: Header redesign (EN) */}
      <section className="flex flex-col gap-2">
        <Link to="/rides" className="text-sm text-slate-500 hover:text-slate-700 w-fit">
          ← Back to Rides
        </Link>

        <h1 className="text-[24px] font-bold text-slate-800">{name}</h1>

        <div className="text-[14px] text-slate-500">
          {new Date(`${date}T12:00:00`).toLocaleDateString("en-GB", {
            day: "numeric",
            month: "short",
            year: "numeric",
          })}{" "}
          · {rideType}
        </div>

        <div className="text-[14px] text-slate-500">
          {(distanceM / 1000).toFixed(1)} km · {Math.round(durationS / 60)} min ·{" "}
          {Math.round(precisionWatt)} W avg
        </div>

        <div className="mt-1 text-[14px] italic text-emerald-600">
          ⚡ Analyzed with Precision Watt (beta)
        </div>
      </section>

      {/* Patch 3B.3: Power over time graph */}
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-2 text-sm font-medium text-slate-700">Power over time</div>

        <svg viewBox="0 0 300 100" className="w-full h-[300px]">
          <polyline
            fill="none"
            stroke="#10b981"
            strokeWidth="2"
            points={powerSeries
              .map((p, i) => {
                const x = (i / powerSeries.length) * 300;
                const y = 100 - Math.min(100, (p / 300) * 100);
                return `${x},${y}`;
              })
              .join(" ")}
          />
        </svg>

        <div className="mt-2 text-xs text-slate-400">
          *Illustrative curve (deterministic), not raw timeseries.
        </div>
      </section>

      {/* Patch 3B.4: Metrics grid (4×2) */}
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-4 text-sm font-medium text-slate-700">Power analysis</div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Metric label="Avg power" value={`${Math.round(precisionWatt)} W`} />
          <Metric
            label="Normalized power"
            value={Number.isFinite(stravaWatt) ? `${Math.round(stravaWatt)} W` : "—"}
          />
          <Metric
            label="Elevation gain"
            value={Number.isFinite(elevation) ? `${Math.round(elevation)} m` : "—"}
          />
          <Metric
            label="Avg speed"
            value={Number.isFinite(avgSpeed) ? `${avgSpeed.toFixed(1)} km/h` : "—"}
          />

          <Metric
            label="Rider weight"
            value={Number.isFinite(riderWeight) ? `${riderWeight.toFixed(1)} kg` : "—"}
          />
          <Metric
            label="Temperature"
            value={
              typeof tempVal === "number" && Number.isFinite(tempVal) ? `${tempVal} °C` : "— °C"
            }
          />
          <Metric
            label="Wind speed"
            value={
              typeof windSpeedVal === "number" && Number.isFinite(windSpeedVal)
                ? `${windSpeedVal} m/s`
                : "— m/s"
            }
          />
          <Metric label="Conditions" value={typeof conditionsVal === "string" ? conditionsVal : "—"} />
        </div>
      </section>

      {/* Keep navigation buttons */}
      <section className="flex gap-3">
        <Link
          to="/rides"
          className="px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50"
        >
          ← Back to Rides
        </Link>
        <Link
          to="/dashboard"
          className="px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50"
        >
          Dashboard
        </Link>
      </section>
    </div>
  );
};

const RealSessionView: React.FC = () => {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const location = useLocation();

  const { currentSession, loadingSession, errorSession, loadSession, clearCurrentSession } =
    useSessionStore();

  // Last session via store, og rydd på unmount / ved id-bytt
  useEffect(() => {
    if (!id) return;

    clearCurrentSession();
    loadSession(id);

    return () => {
      clearCurrentSession();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const title = useMemo(() => (id ? `Økt #${id}` : "Økt"), [id]);
  const sourceLabel = id === "mock" ? "MOCK (lokale testdata)" : "LIVE fra backend";

  // ─────────────────────────────────────────────────────────────
  // Patch: localStorage profile override (kun rider_weight_kg)
  // ─────────────────────────────────────────────────────────────
  function readLocalProfileOverride(): any | null {
    try {
      const raw = localStorage.getItem("cg.profile.v1");
      if (!raw) return null;

      const p = JSON.parse(raw);

      // Vi ønsker å sende rider_weight_kg til backend (ikke total weight_kg).
      // Mange steder lagrer UI bare weight_kg → map til rider_weight_kg.
      const rider =
        typeof p.rider_weight_kg === "number"
          ? p.rider_weight_kg
          : typeof p.weight_kg === "number"
          ? p.weight_kg
          : undefined;

      const bike = typeof p.bike_weight_kg === "number" ? p.bike_weight_kg : undefined;

      const out: any = {};

      if (typeof rider === "number") out.rider_weight_kg = rider;
      if (typeof bike === "number") out.bike_weight_kg = bike;

      // ta med aero/rulle hvis de finnes
      if (typeof p.cda === "number") out.cda = p.cda;
      if (typeof p.crr === "number") out.crr = p.crr;

      // crank-eff kan du sende om du vil, men ikke nødvendig for denne feilen
      if (typeof p.crank_efficiency === "number") out.crank_efficiency = p.crank_efficiency;
      if (typeof p.crank_eff_pct === "number") out.crank_eff_pct = p.crank_eff_pct;

      return out;
    } catch {
      return null;
    }
  }

  // ─────────────────────────────────────────────────────
  // Patch: state + handler for Re-analyze
  // ─────────────────────────────────────────────────────
  const [reAnalyzing, setReAnalyzing] = React.useState(false);

  async function reAnalyzeNow() {
    if (!id) return;
    const override = readLocalProfileOverride();
    if (!override) {
      console.warn("[SessionView] no local profile override found");
      return;
    }

    setReAnalyzing(true);
    try {
      // Viktig: krever at loadSession støtter opts: { forceRecompute, profileOverride }
      await loadSession(id, { forceRecompute: true, profileOverride: override } as any);
    } finally {
      setReAnalyzing(false);
    }
  }

  // ─────────────────────────────────────────────────────────────
  // ✅ Patch: Auto re-analyze ved profile_version mismatch (NOOP midlertidig)
  // ─────────────────────────────────────────────────────────────
  // NOTE: beholdt ref + effect for debugging/logging, men vi trigger IKKE loadSession().
  // MIDDELTIDIG: disable auto re-analyze, den skaper request-storm + timeout
  const autoKeyRef = useRef<string>("");

  useEffect(() => {
    (async () => {
      const s = currentSession as any;
      const sid = String(params.id ?? "");
      if (!sid || !s) return;

      // 1) Hent UI profile_version (safe)
      const ui = await cgApi.profileGet().catch(() => null);
      const uiPv = String((ui as any)?.profile_version ?? "");

      // 2) Finn "usedPv" fra analyze-respons (toppnivå først)
      const usedPv =
        String(s?.profile_version ?? "") || String(s?.metrics?.profile_used?.profile_version ?? "");

      if (!uiPv || !usedPv) return;

      // 3) Guard: maks én log per (id + uiPv) i StrictMode
      const key = `${sid}::${uiPv}`;
      if (autoKeyRef.current === key) return;

      if (uiPv !== usedPv) {
        autoKeyRef.current = key;

        console.log("[SessionView] Auto re-analyze DISABLED (profile_version mismatch)", {
          id: sid,
          uiPv,
          usedPv,
        });

        // NOOP:
        // await loadSession(sid, { forceRecompute: true } as any);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSession, params.id]);

  // ─────────────────────────────────────────────────────
  // Tydelig rendering state – ingen silent fallback
  // ─────────────────────────────────────────────────────
  if (!id) {
    return (
      <div className="p-4">
        <ErrorBanner message="Mangler økt-id i URL." onRetry={() => window.history.back()} />
      </div>
    );
  }

  if (loadingSession) {
    return (
      <div className="session-view max-w-4xl mx-auto px-4 py-6">
        <div className="text-sm text-slate-500">Laster analyse for denne økten…</div>
      </div>
    );
  }

  if (errorSession) {
    return (
      <div className="session-view max-w-4xl mx-auto px-4 py-6 space-y-4">
        <ErrorBanner message={errorSession} onRetry={() => loadSession(id)} />
        <Link className="underline" to={ROUTES.RIDES}>
          ← Tilbake til økter
        </Link>
      </div>
    );
  }

  if (!currentSession) {
    return (
      <div className="session-view max-w-4xl mx-auto px-4 py-6 space-y-4">
        <div className="text-sm text-slate-500">Ingen øktdata tilgjengelig ennå.</div>
        <Link className="underline" to={ROUTES.RIDES}>
          ← Tilbake til økter
        </Link>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────
  // Vi har data (Analyze-SSOT)
  // ─────────────────────────────────────────────────────
  const session: SessionReport = currentSession;

  // Analyze-responsen har precision_watt_avg top-level
  const precisionAvg = (session as any)?.precision_watt_avg ?? null;

  // metrics (total_watt, drag_watt, osv.) kan ligge i session.metrics
  const metrics: any = (session as any)?.metrics ?? null;

  const profileUsed: any = metrics?.profile_used ?? (session as any)?.profile_used ?? null;
  const weatherUsed: any = metrics?.weather_used ?? null;

  const totalWeight: unknown = profileUsed ? profileUsed.total_weight_kg ?? profileUsed.weight_kg : undefined;

  return (
    <div className="session-view max-w-4xl mx-auto px-4 py-6 space-y-6">
      {/* HEADER */}
      <header className="flex items-start justify-between gap-4 border-b pb-4">
        <div>
          <h1 className="text-2xl font-semibold mb-1">{title}</h1>
          <p className="text-sm text-slate-500">Kilde: {sourceLabel}</p>

          {location.state && (location.state as any).from === "sessions" && (
            <p className="text-xs text-slate-400 mt-1">Navigert hit fra øktlisten.</p>
          )}
        </div>

        <div className="text-right">
          <div className="flex items-center justify-end">
            <Link
              to={ROUTES.RIDES}
              className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-slate-50"
            >
              ← Tilbake til økter
            </Link>

            {/* Patch: Re-analyze-knapp (med hard logging) */}
            <button
              onClick={() => {
                const override = readLocalProfileOverride();
                console.log("[SessionView] reAnalyzeNow override =", override);
                console.log("[SessionView] reAnalyzeNow rider_weight_kg =", override?.rider_weight_kg);
                reAnalyzeNow();
              }}
              disabled={reAnalyzing}
              className="ml-2 inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
              title="Re-analyser økta med rider_weight_kg fra localStorage (cg.profile.v1)"
            >
              {reAnalyzing ? "Re-analyserer…" : "Re-analyser med ny vekt"}
            </button>
          </div>
        </div>
      </header>

      {/* HOVEDINNHOLD */}
      <div className="space-y-6">
        {/* METRICS-SEKSJON */}
        {metrics ? (
          <section className="border rounded-lg p-4 space-y-3">
            <h2 className="text-lg font-semibold">Analyse – Precision Watt</h2>

            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2 text-sm">
              <div>
                <dt className="text-slate-500">Precision watt (snitt, fra analyze)</dt>
                <dd className="font-medium">{fmtW(precisionAvg)}</dd>
              </div>

              <div>
                <dt className="text-slate-500">Total watt</dt>
                <dd className="font-medium">{fmtW(metrics.total_watt)}</dd>
              </div>

              <div>
                <dt className="text-slate-500">Drag watt</dt>
                <dd className="font-medium">{fmtW(metrics.drag_watt)}</dd>
              </div>

              <div>
                <dt className="text-slate-500">Rolling watt</dt>
                <dd className="font-medium">{fmtW(metrics.rolling_watt)}</dd>
              </div>

              <div>
                <dt className="text-slate-500">Gravity watt</dt>
                <dd className="font-medium">{fmtW((metrics as any).gravity_watt)}</dd>
              </div>

              <div>
                <dt className="text-slate-500">Kalibrert mot wattmåler</dt>
                <dd className="font-medium">
                  {metrics.calibrated ? "Ja" : "Nei"}
                  {num(metrics.calibration_mae) !== null
                    ? ` (MAE ≈ ${num(metrics.calibration_mae)!.toFixed(1)} W)`
                    : ""}
                </dd>
              </div>
            </dl>
          </section>
        ) : (
          <p className="text-sm text-slate-500">Ingen analyse-data tilgjengelig for denne økten ennå.</p>
        )}

        {/* PROFIL-INFO */}
        {profileUsed && (
          <section className="border rounded-lg p-4 space-y-2 text-sm">
            <h2 className="text-lg font-semibold">Profil brukt i analysen</h2>

            <p className="text-slate-500">
              Versjon: <span className="font-mono">{profileUsed.profile_version ?? "ukjent"}</span>
            </p>

            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1">
              <div>
                <dt className="text-slate-500">Totalvekt (rider + sykkel)</dt>
                <dd className="font-medium">{fmtKg(totalWeight)}</dd>
              </div>

              <div>
                <dt className="text-slate-500">CdA</dt>
                <dd className="font-medium">{profileUsed.cda ?? "—"}</dd>
              </div>

              <div>
                <dt className="text-slate-500">Crr</dt>
                <dd className="font-medium">{profileUsed.crr ?? "—"}</dd>
              </div>

              <div>
                <dt className="text-slate-500">Enhet / device</dt>
                <dd className="font-medium">{profileUsed.device ?? "ukjent"}</dd>
              </div>
            </dl>
          </section>
        )}

        {/* VÆR-INFO */}
        {weatherUsed && (
          <section className="border rounded-lg p-4 space-y-2 text-sm">
            <h2 className="text-lg font-semibold">Vær brukt i analysen</h2>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1">
              <div>
                <dt className="text-slate-500">Vind</dt>
                <dd className="font-medium">
                  {fmtMs(weatherUsed.wind_ms)}{" "}
                  {num(weatherUsed.wind_dir_deg) !== null
                    ? `fra ${num(weatherUsed.wind_dir_deg)!.toFixed(0)}°`
                    : ""}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Temperatur</dt>
                <dd className="font-medium">{fmtC(weatherUsed.air_temp_c)}</dd>
              </div>

              <div>
                <dt className="text-slate-500">Lufttrykk</dt>
                <dd className="font-medium">{fmtHpa(weatherUsed.air_pressure_hpa)}</dd>
              </div>
            </dl>
          </section>
        )}
      </div>
    </div>
  );
};

const SessionView: React.FC = () => {
  return isDemoMode() ? <DemoSessionView /> : <RealSessionView />;
};

export default SessionView;
