// frontend/src/pages/SessionView.tsx
import React, { useEffect, useMemo } from "react";
import { useParams, Link, useLocation } from "react-router-dom";

import { useSessionStore } from "../state/sessionStore";
import type { SessionReport } from "../types/session";

import ErrorBanner from "../components/ErrorBanner";
import { ROUTES } from "../lib/routes";

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

const SessionView: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();

  const {
    currentSession,
    loadingSession,
    errorSession,
    loadSession,
    clearCurrentSession,
  } = useSessionStore();

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

  const profileUsed: any = metrics?.profile_used ?? null;
  const weatherUsed: any = metrics?.weather_used ?? null;

  const totalWeight: unknown = profileUsed
    ? profileUsed.total_weight_kg ?? profileUsed.weight_kg
    : undefined;

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
                console.log(
                  "[SessionView] reAnalyzeNow rider_weight_kg =",
                  override?.rider_weight_kg
                );
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
          <p className="text-sm text-slate-500">
            Ingen analyse-data tilgjengelig for denne økten ennå.
          </p>
        )}

        {/* PROFIL-INFO */}
        {profileUsed && (
          <section className="border rounded-lg p-4 space-y-2 text-sm">
            <h2 className="text-lg font-semibold">Profil brukt i analysen</h2>

            <p className="text-slate-500">
              Versjon:{" "}
              <span className="font-mono">{profileUsed.profile_version ?? "ukjent"}</span>
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

export default SessionView;
