import React, { useEffect, useMemo, useState } from "react";
import { useParams, Link, useLocation } from "react-router-dom";

import type { SessionReport } from "../types/session";
import { fetchSession } from "../lib/api";
import type { FetchSessionResult } from "../lib/api";

import ErrorBanner from "../components/ErrorBanner";
import CalibrationGuide from "../components/CalibrationGuide";

const SessionView: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();

  const [session, setSession] = useState<SessionReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<"mock" | "live" | null>(null);

  // ─────────────────────────────────────────────────────
  // HENT ØKT FRA BACKEND VIA api.fetchSession
  // ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!id) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const res: FetchSessionResult = await fetchSession(id);
        if (cancelled) return;

        if (res.ok) {
          setSession(res.data);
          setSource(res.source);
        } else {
          setSession(null);
          setSource(res.source ?? null);
          setError(res.error || "Klarte ikke å hente økt.");
        }
      } catch (e) {
        if (cancelled) return;
        setSession(null);
        setSource(null);
        setError(`Uventet feil: ${String(e)}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [id]);

  const title = useMemo(
    () => (id ? `Økt #${id}` : "Økt"),
    [id]
  );

  const metrics = session?.metrics ?? null;
  const profileUsed: any = metrics && (metrics as any).profile_used;
  const weatherUsed: any = metrics && (metrics as any).weather_used;

  if (!id) {
    return <ErrorBanner message="Mangler økt-id i URL." />;
  }

  return (
    <div className="session-view max-w-4xl mx-auto px-4 py-6 space-y-6">
      {/* HEADER */}
      <header className="flex items-start justify-between gap-4 border-b pb-4">
        <div>
          <h1 className="text-2xl font-semibold mb-1">{title}</h1>
          <p className="text-sm text-slate-500">
            Kilde:{" "}
            {source === "mock"
              ? "MOCK (lokale testdata)"
              : source === "live"
              ? "LIVE fra backend"
              : "ukjent"}
          </p>
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

      {/* LOADING / ERROR */}
      {loading && (
        <p className="text-sm text-slate-500">Laster analyse for denne økten…</p>
      )}

      {error && (
        <ErrorBanner message={error} />
      )}

      {/* HOVEDINNHOLD NÅR VI HAR DATA */}
      {!loading && !error && session && (
        <div className="space-y-6">
          {/* METRICS-SEKSJON */}
          {metrics ? (
            <section className="border rounded-lg p-4 space-y-3">
              <h2 className="text-lg font-semibold">
                Analyse – Precision Watt
              </h2>
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
                    {typeof metrics.calibration_mae === "number" &&
                      ` (MAE ≈ ${metrics.calibration_mae.toFixed(1)} W)`}
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
                    {profileUsed.total_weight_kg ?? profileUsed.weight_kg
                      ? `${(profileUsed.total_weight_kg ??
                          profileUsed.weight_kg).toFixed(1)} kg`
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500">CdA</dt>
                  <dd className="font-medium">
                    {profileUsed.cda ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500">Crr</dt>
                  <dd className="font-medium">
                    {profileUsed.crr ?? "—"}
                  </dd>
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

          {/* KALIBRERINGS-GUIDE (kan ligge her inntil egen side er 100%) */}
          <section className="border rounded-lg p-4">
            <CalibrationGuide />
          </section>
        </div>
      )}
    </div>
  );
};

export default SessionView;
