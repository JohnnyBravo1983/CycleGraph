// frontend/src/pages/SessionView.tsx
import React, { useEffect, useMemo } from "react";
import { useParams, Link, useLocation } from "react-router-dom";

import { useSessionStore } from "../state/sessionStore";
import type { SessionReport } from "../types/session";

import ErrorBanner from "../components/ErrorBanner";
import { ROUTES } from "../lib/routes";

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

  // ─────────────────────────────────────────────────────
  // Tydelig rendering state – ingen silent fallback
  // ─────────────────────────────────────────────────────
  if (!id) {
    return (
      <div className="p-4">
        <ErrorBanner
          message="Mangler økt-id i URL."
          onRetry={() => window.history.back()}
        />
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
  // Vi har data
  // ─────────────────────────────────────────────────────
  const session: SessionReport = currentSession;

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
          <Link
            to={ROUTES.RIDES}
            className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-slate-50"
          >
            ← Tilbake til økter
          </Link>
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
                <dt className="text-slate-500">Precision watt (snitt)</dt>
                <dd className="font-medium">
                  {typeof metrics.precision_watt === "number"
                    ? `${metrics.precision_watt.toFixed(1)} W`
                    : "—"}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Total watt</dt>
                <dd className="font-medium">
                  {typeof metrics.total_watt === "number"
                    ? `${metrics.total_watt.toFixed(1)} W`
                    : "—"}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Drag watt</dt>
                <dd className="font-medium">
                  {typeof metrics.drag_watt === "number"
                    ? `${metrics.drag_watt.toFixed(1)} W`
                    : "—"}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Rolling watt</dt>
                <dd className="font-medium">
                  {typeof metrics.rolling_watt === "number"
                    ? `${metrics.rolling_watt.toFixed(1)} W`
                    : "—"}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Gravity watt</dt>
                <dd className="font-medium">
                  {typeof (metrics as any).gravity_watt === "number"
                    ? `${(metrics as any).gravity_watt.toFixed(1)} W`
                    : "—"}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Kalibrert mot wattmåler</dt>
                <dd className="font-medium">
                  {metrics.calibrated ? "Ja" : "Nei"}
                  {typeof metrics.calibration_mae === "number"
                    ? ` (MAE ≈ ${metrics.calibration_mae.toFixed(1)} W)`
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
                <dd className="font-medium">
                  {typeof totalWeight === "number" ? `${totalWeight.toFixed(1)} kg` : "—"}
                </dd>
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
                  {typeof weatherUsed.wind_ms === "number"
                    ? `${weatherUsed.wind_ms.toFixed(1)} m/s`
                    : "—"}{" "}
                  {typeof weatherUsed.wind_dir_deg === "number"
                    ? `fra ${weatherUsed.wind_dir_deg.toFixed(0)}°`
                    : ""}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Temperatur</dt>
                <dd className="font-medium">
                  {typeof weatherUsed.air_temp_c === "number"
                    ? `${weatherUsed.air_temp_c.toFixed(1)} °C`
                    : "—"}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Lufttrykk</dt>
                <dd className="font-medium">
                  {typeof weatherUsed.air_pressure_hpa === "number"
                    ? `${weatherUsed.air_pressure_hpa.toFixed(0)} hPa`
                    : "—"}
                </dd>
              </div>
            </dl>
          </section>
        )}
      </div>
    </div>
  );
};

export default SessionView;
