// frontend/src/pages/SessionView.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useParams, Link, useLocation } from "react-router-dom";

import { useSessionStore } from "../state/sessionStore";
import type { SessionReport } from "../types/session";

import ErrorBanner from "../components/ErrorBanner";
import CalibrationGuide from "../components/CalibrationGuide";

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

  // Calibration modal state
  const [calOpen, setCalOpen] = useState(false);

  // Én-gangs logging av source (heuristikk for MVP)
  const loggedRef = useRef<string | null>(null);
  useEffect(() => {
    if (!id) return;

    const src = id === "mock" ? "mock" : "live";
    const key = `${id}:${src}`;

    if (loggedRef.current !== key) {
      console.info("[SessionView] source:", src, "id:", id);
      loggedRef.current = key;
    }
  }, [id]);

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
  const sourceLabel =
    id === "mock" ? "MOCK (lokale testdata)" : "LIVE fra backend";

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
        <div className="text-sm text-slate-500">
          Laster analyse for denne økten…
        </div>
      </div>
    );
  }

  if (errorSession) {
    return (
      <div className="session-view max-w-4xl mx-auto px-4 py-6 space-y-4">
        <ErrorBanner message={errorSession} onRetry={() => loadSession(id)} />
        <Link className="underline" to="/rides">
          ← Tilbake til økter
        </Link>
      </div>
    );
  }

  if (!currentSession) {
    return (
      <div className="session-view max-w-4xl mx-auto px-4 py-6 space-y-4">
        <div className="text-sm text-slate-500">
          Ingen øktdata tilgjengelig ennå.
        </div>
        <Link className="underline" to="/rides">
          ← Tilbake til økter
        </Link>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────
  // Vi har data – DEBUG (nøyaktig hva som ligger hvor)
  // ─────────────────────────────────────────────────────
  const session: SessionReport = currentSession;

  // Dette er “best guess” basert på tidligere struktur.
  const metrics: any = (session as any)?.metrics ?? null;
  const profileUsed: any = metrics?.profile_used ?? null;
  const weatherUsed: any = metrics?.weather_used ?? null;

  // Debug logs (skrives hver render når vi har session)
  // NB: Hvis dette blir for spammy kan vi senere gate på en queryparam.
  try {
    console.log("[SessionView][DEBUG] session keys:", Object.keys(session as any));
    console.log("[SessionView][DEBUG] session.metrics:", (session as any).metrics);
    console.log(
      "[SessionView][DEBUG] metrics keys:",
      Object.keys((((session as any).metrics ?? {}) as any) || {})
    );
    console.log("[SessionView][DEBUG] full session:", session);
  } catch {
    // ignore
  }

  const totalWeight: unknown = profileUsed
    ? profileUsed.total_weight_kg ?? profileUsed.weight_kg
    : undefined;

  const isMock = id === "mock";

  return (
    <div className="session-view max-w-4xl mx-auto px-4 py-6 space-y-6">
      {/* HEADER */}
      <header className="flex items-start justify-between gap-4 border-b pb-4">
        <div>
          <h1 className="text-2xl font-semibold mb-1">{title}</h1>
          <p className="text-sm text-slate-500">Kilde: {sourceLabel}</p>

          {location.state && (location.state as any).from === "sessions" && (
            <p className="text-xs text-slate-400 mt-1">
              Navigert hit fra øktlisten.
            </p>
          )}
        </div>

        <div className="text-right">
          <Link
            to="/rides"
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
              <span className="font-mono">
                {profileUsed.profile_version ?? "ukjent"}
              </span>
            </p>

            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1">
              <div>
                <dt className="text-slate-500">Totalvekt (rider + sykkel)</dt>
                <dd className="font-medium">
                  {typeof totalWeight === "number"
                    ? `${totalWeight.toFixed(1)} kg`
                    : "—"}
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
                <dd className="font-medium">
                  {profileUsed.device ?? "ukjent"}
                </dd>
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

        {/* KALIBRERING */}
        <section className="border rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Kalibrering</h2>
            <button
              type="button"
              onClick={() => setCalOpen(true)}
              className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-slate-50"
            >
              Åpne guide
            </button>
          </div>

          <CalibrationGuide
            sessionId={id}
            isOpen={calOpen}
            onClose={() => setCalOpen(false)}
            onCalibrated={() => {
              setCalOpen(false);
              loadSession(id); // refresh view
            }}
            isMock={isMock}
          />
        </section>

        {/* DEBUG PANEL (visuelt) */}
        <section className="border rounded-lg p-4 space-y-2 text-xs">
          <div className="font-semibold">DEBUG</div>
          <div>
            <span className="text-slate-500">session keys:</span>{" "}
            {Object.keys(session as any).join(", ")}
          </div>
          <div>
            <span className="text-slate-500">metrics exists:</span>{" "}
            {metrics ? "yes" : "no"}
          </div>
          <div>
            <span className="text-slate-500">metrics keys:</span>{" "}
            {metrics ? Object.keys(metrics as any).join(", ") : "—"}
          </div>
        </section>
      </div>
    </div>
  );
};

export default SessionView;
