// frontend/src/routes/SessionView.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useParams, Link, useLocation } from "react-router-dom";

import { useSessionStore } from "../state/sessionStore";
import type { SessionReport } from "../types/session";

import ErrorBanner from "../components/ErrorBanner";
import { ROUTES } from "../lib/routes";
import { cgApi } from "../lib/cgApi";

import { isDemoMode } from "../demo/demoMode";
import { demoRides } from "../demo/demoRides";

// ─────────────────────────────────────────────────────────────
// Helpers: safe object access (unknown → typed)
// ─────────────────────────────────────────────────────────────
type UnknownRecord = Record<string, unknown>;

function isRecord(v: unknown): v is UnknownRecord {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function getNested(obj: unknown, path: string[]): unknown {
  let cur: unknown = obj;
  for (const key of path) {
    if (!isRecord(cur)) return undefined;
    cur = cur[key];
  }
  return cur;
}

// ✅ Render-safe formatter: aldri returner object/unknown til JSX
function fmtNode(v: unknown, fallback = "—"): string {
  if (v === null || v === undefined) return fallback;
  if (typeof v === "string") return v.length ? v : fallback;
  if (typeof v === "number") return Number.isFinite(v) ? String(v) : fallback;
  if (typeof v === "boolean") return v ? "Yes" : "No";
  return fallback;
}

// ─────────────────────────────────────────────────────────────
// Helpers (tåler number og string med komma/punktum)
// ─────────────────────────────────────────────────────────────
function num(x: unknown): number | null {
  if (typeof x === "number") return Number.isFinite(x) ? x : null;
  if (typeof x === "string") {
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
// Demo ride shape (kun det vi faktisk bruker i viewet)
// ─────────────────────────────────────────────────────────────
type DemoRide = {
  id: string | number;
  name?: string;
  date?: string; // "YYYY-MM-DD"
  rideType?: string;
  distance?: number; // meters
  duration?: number; // seconds
  precisionWatt?: number;
  stravaWatt?: number;
  elevation?: number;
  avgSpeed?: number; // km/h
  riderWeight?: number;
  weather?: {
    temp?: number;
    conditions?: string;
    wind?: {
      speed?: number;
    };
  };
};

// ─────────────────────────────────────────────────────────────
// Metric card (DemoSessionView)
// ─────────────────────────────────────────────────────────────
const Metric = ({ label, value }: { label: string; value: string }) => (
  <div className="border border-slate-200 rounded-lg p-4">
    <div className="text-[12px] uppercase tracking-wide text-slate-500">
      {label}
    </div>
    <div className="mt-1 text-[18px] font-semibold text-slate-800">{value}</div>
  </div>
);

// ─────────────────────────────────────────────────────────────
// Demo view (ingen backend-kall)
// ─────────────────────────────────────────────────────────────
const DemoSessionView: React.FC = () => {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";

  const ride = useMemo<DemoRide | null>(() => {
    const list = demoRides as unknown as DemoRide[];
    if (!id) return null;
    const found = list.find((r) => String(r.id) === String(id));
    return found ?? null;
  }, [id]);

  const powerSeries = useMemo<number[]>(() => {
    if (!ride) return [];
    const minutes = Math.max(10, Math.round((ride.duration ?? 0) / 60));
    const pw = typeof ride.precisionWatt === "number" ? ride.precisionWatt : 0;

    const base = ride.rideType === "long-ride" ? pw : pw * 1.1;

    return Array.from({ length: minutes }, (_, i) => {
      const noise = Math.sin(i / 5) * 6;
      return Math.max(80, base + noise);
    });
  }, [ride]);

  const name = ride?.name ?? "Ride";
  const date = ride?.date ?? "";
  const rideType = (ride?.rideType ?? "ride").replace("-", " ");

  const distanceM = ride?.distance ?? 0;
  const durationS = ride?.duration ?? 0;
  const precisionWatt = ride?.precisionWatt ?? 0;

  const stravaWatt = ride?.stravaWatt;
  const elevation = ride?.elevation;
  const avgSpeed = ride?.avgSpeed;
  const riderWeight = ride?.riderWeight;

  const tempVal = ride?.weather?.temp;
  const windSpeedVal = ride?.weather?.wind?.speed;
  const conditionsVal = ride?.weather?.conditions;

  if (!id) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Session</h1>
        <div className="rounded-xl border bg-white p-4 text-slate-700">
          Missing session id in URL.
        </div>
        <div className="flex gap-3">
          <Link
            to="/rides"
            className="px-4 py-2 rounded-xl border bg-white hover:bg-slate-50"
          >
            ← Back to Rides
          </Link>
          <Link
            to="/dashboard"
            className="px-4 py-2 rounded-xl border bg-white hover:bg-slate-50"
          >
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
          Could not find demo ride with ID{" "}
          <span className="font-mono">{id}</span>.
        </div>
        <div className="flex gap-3">
          <Link
            to="/rides"
            className="px-4 py-2 rounded-xl border bg-white hover:bg-slate-50"
          >
            ← Back to Rides
          </Link>
          <Link
            to="/dashboard"
            className="px-4 py-2 rounded-xl border bg-white hover:bg-slate-50"
          >
            Dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <section className="flex flex-col gap-2">
        <Link
          to="/rides"
          className="text-sm text-slate-500 hover:text-slate-700 w-fit"
        >
          ← Back to Rides
        </Link>

        <h1 className="text-[24px] font-bold text-slate-800">{name}</h1>

        <div className="text-[14px] text-slate-500">
          {date
            ? new Date(`${date}T12:00:00`).toLocaleDateString("en-GB", {
                day: "numeric",
                month: "short",
                year: "numeric",
              })
            : "—"}{" "}
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

      {/* Power over time graph */}
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-2 text-sm font-medium text-slate-700">
          Power over time
        </div>

        <svg viewBox="0 0 300 100" className="w-full h-[300px]">
          <polyline
            fill="none"
            stroke="#10b981"
            strokeWidth="2"
            points={powerSeries
              .map((p, i) => {
                const x = (i / Math.max(1, powerSeries.length - 1)) * 300;
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

      {/* Metrics grid */}
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-4 text-sm font-medium text-slate-700">
          Power analysis
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Metric label="Avg power" value={`${Math.round(precisionWatt)} W`} />
          <Metric
            label="Normalized power"
            value={
              typeof stravaWatt === "number" && Number.isFinite(stravaWatt)
                ? `${Math.round(stravaWatt)} W`
                : "—"
            }
          />
          <Metric
            label="Elevation gain"
            value={
              typeof elevation === "number" && Number.isFinite(elevation)
                ? `${Math.round(elevation)} m`
                : "—"
            }
          />
          <Metric
            label="Avg speed"
            value={
              typeof avgSpeed === "number" && Number.isFinite(avgSpeed)
                ? `${avgSpeed.toFixed(1)} km/h`
                : "—"
            }
          />

          <Metric
            label="Rider weight"
            value={
              typeof riderWeight === "number" && Number.isFinite(riderWeight)
                ? `${riderWeight.toFixed(1)} kg`
                : "—"
            }
          />
          <Metric
            label="Temperature"
            value={
              typeof tempVal === "number" && Number.isFinite(tempVal)
                ? `${tempVal} °C`
                : "— °C"
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
          <Metric
            label="Conditions"
            value={typeof conditionsVal === "string" ? conditionsVal : "—"}
          />
        </div>
      </section>

      {/* Navigation */}
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

// ─────────────────────────────────────────────────────────────
// Real view (backend)
// ─────────────────────────────────────────────────────────────
type ProfileOverride = {
  rider_weight_kg?: number;
  bike_weight_kg?: number;
  cda?: number;
  crr?: number;
  crank_efficiency?: number;
  crank_eff_pct?: number;
};

type LoadSessionOptions = {
  forceRecompute?: boolean;
  profileOverride?: ProfileOverride;
};

const RealSessionView: React.FC = () => {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const location = useLocation();

  const {
    currentSession,
    loadingSession,
    errorSession,
    loadSession,
    clearCurrentSession,
  } = useSessionStore();

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

  function readLocalProfileOverride(): ProfileOverride | null {
    try {
      const raw = localStorage.getItem("cg.profile.v1");
      if (!raw) return null;

      const parsed: unknown = JSON.parse(raw);
      if (!isRecord(parsed)) return null;

      const rider =
        typeof (parsed as any).rider_weight_kg === "number"
          ? (parsed as any).rider_weight_kg
          : typeof (parsed as any).weight_kg === "number"
            ? (parsed as any).weight_kg
            : undefined;

      const bike =
        typeof (parsed as any).bike_weight_kg === "number"
          ? (parsed as any).bike_weight_kg
          : undefined;

      const out: ProfileOverride = {};

      if (typeof rider === "number") out.rider_weight_kg = rider;
      if (typeof bike === "number") out.bike_weight_kg = bike;

      if (typeof (parsed as any).cda === "number") out.cda = (parsed as any).cda;
      if (typeof (parsed as any).crr === "number") out.crr = (parsed as any).crr;

      if (typeof (parsed as any).crank_efficiency === "number")
        out.crank_efficiency = (parsed as any).crank_efficiency;
      if (typeof (parsed as any).crank_eff_pct === "number")
        out.crank_eff_pct = (parsed as any).crank_eff_pct;

      return out;
    } catch {
      return null;
    }
  }

  const [reAnalyzing, setReAnalyzing] = useState(false);

  // ✅ PATCH 2: UI state for Strava 429 detail
  const [rateLimitDetail, setRateLimitDetail] = useState<any | null>(null);

  async function reAnalyzeNow() {
    if (!id) return;

    // ✅ PATCH 2: reset banner first
    setRateLimitDetail(null);

    const override = readLocalProfileOverride();
    if (!override) {
      console.warn("[SessionView] no local profile override found");
      return;
    }

    try {
      setReAnalyzing(true);

      // ✅ Use existing store loader as the canonical way to (re)fetch analyze.
      // It will POST /api/sessions/:id/analyze and refresh currentSession.
      // If your store supports options, pass them; otherwise it will just re-run analyze.
      const result: any = await (async () => {
        try {
          // Try: loadSession(id, options) if implemented
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const maybe: any = loadSession as any;
          if (typeof maybe === "function" && maybe.length >= 2) {
            return await maybe(id, {
              forceRecompute: true,
              profileOverride: override,
            } as LoadSessionOptions);
          }
          // fallback: call without options (still re-analyzes)
          return await maybe(id);
        } catch (e) {
          throw e;
        }
      })();

      // ✅ PATCH 2: if analyze returns structured rate-limit error (from api.ts)
      if (
        result &&
        result.ok === false &&
        result.source === "live" &&
        result.error === "STRAVA_RATE_LIMITED"
      ) {
        setRateLimitDetail((result as any).detail ?? {});
        return;
      }

      // If loadSession doesn't return anything, that's fine — state updates via store.
      // Banner remains null on success.
    } catch (e: any) {
      const msg = String(e?.message ?? "");

      // if caller throws a structured object
      if (e?.error === "STRAVA_RATE_LIMITED") {
        setRateLimitDetail(e?.detail ?? {});
        return;
      }

      // heuristics fallback
      if (
        e?.status === 429 ||
        msg.includes("429") ||
        msg.includes("STRAVA_RATE_LIMITED") ||
        msg.includes("strava_rate_limited")
      ) {
        const d = e?.detail ?? e?.response?.detail ?? {};
        setRateLimitDetail(d);
        return;
      }

      console.log("[SessionView] reAnalyzeNow error:", e);
    } finally {
      setReAnalyzing(false);
    }
  }

  // Auto re-analyze ved profile_version mismatch (NOOP midlertidig)
  const autoKeyRef = useRef<string>("");

  useEffect(() => {
    (async () => {
      const s: unknown = currentSession;
      const sid = String(params.id ?? "");
      if (!sid || !s) return;

      const ui = await cgApi.profileGet().catch(() => null);
      const uiPv = String(
        (ui as unknown as { profile_version?: unknown } | null)?.profile_version ??
          ""
      );

      const usedPv =
        String(getNested(s, ["profile_version"]) ?? "") ||
        String(getNested(s, ["metrics", "profile_used", "profile_version"]) ?? "");

      if (!uiPv || !usedPv) return;

      const key = `${sid}::${uiPv}`;
      if (autoKeyRef.current === key) return;

      if (uiPv !== usedPv) {
        autoKeyRef.current = key;
        console.log(
          "[SessionView] Auto re-analyze DISABLED (profile_version mismatch)",
          { id: sid, uiPv, usedPv }
        );
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSession, params.id]);

  // Rendering states
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
        <Link className="underline" to={ROUTES.RIDES}>
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
        <Link className="underline" to={ROUTES.RIDES}>
          ← Tilbake til økter
        </Link>
      </div>
    );
  }

  // Analyze-SSOT
  const session: SessionReport = currentSession;

  const precisionAvg = getNested(session, ["precision_watt_avg"]);
  const metrics = getNested(session, ["metrics"]);

  const profileUsed =
    getNested(metrics, ["profile_used"]) ?? getNested(session, ["profile_used"]);
  const weatherUsed = getNested(metrics, ["weather_used"]);

  // ✅ For render: gjør alt til string på forhånd
  const hasProfile = isRecord(profileUsed);

  const profileVersionStr = hasProfile
    ? fmtNode((profileUsed as any).profile_version, "ukjent")
    : "ukjent";

  const totalWeight = hasProfile
    ? ((profileUsed as any).total_weight_kg ?? (profileUsed as any).weight_kg)
    : undefined;

  const cdaStr = hasProfile ? fmtNode((profileUsed as any).cda) : "—";
  const crrStr = hasProfile ? fmtNode((profileUsed as any).crr) : "—";
  const deviceStr = hasProfile
    ? fmtNode((profileUsed as any).device, "ukjent")
    : "ukjent";

  const calibrated = getNested(metrics, ["calibrated"]) === true;

  return (
    <div className="session-view max-w-4xl mx-auto px-4 py-6 space-y-6">
      {/* HEADER */}
      <header className="flex items-start justify-between gap-4 border-b pb-4">
        <div>
          <h1 className="text-2xl font-semibold mb-1">{title}</h1>
          <p className="text-sm text-slate-500">Kilde: {sourceLabel}</p>

          {location.state &&
            isRecord(location.state) &&
            (location.state as any).from === "sessions" && (
              <p className="text-xs text-slate-400 mt-1">
                Navigert hit fra øktlisten.
              </p>
            )}
        </div>

        <div className="text-right">
          {/* ✅ PATCH 2: Banner for Strava 429 */}
          {rateLimitDetail && (
            <div className="mb-3 rounded-xl border border-neutral-300 bg-white p-3 text-left">
              <div className="font-semibold">Strava er midlertidig låst</div>
              <div className="text-sm">
                Prøv igjen om{" "}
                <b>{String(rateLimitDetail.retry_after_seconds ?? 60)}s</b>
                {rateLimitDetail.locked_until_utc ? (
                  <> (locked until: {String(rateLimitDetail.locked_until_utc)})</>
                ) : null}
              </div>
              {rateLimitDetail.reason ? (
                <div className="text-xs opacity-70">
                  Reason: {String(rateLimitDetail.reason)}
                </div>
              ) : null}
            </div>
          )}

          <div className="flex items-center justify-end">
            <Link
              to={ROUTES.RIDES}
              className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-slate-50"
            >
              ← Tilbake til økter
            </Link>

            <button
              onClick={() => {
                const override = readLocalProfileOverride();
                console.log("[SessionView] reAnalyzeNow override =", override);
                console.log(
                  "[SessionView] reAnalyzeNow rider_weight_kg =",
                  override?.rider_weight_kg
                );
                void reAnalyzeNow();
              }}
              disabled={reAnalyzing}
              className="ml-2 inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
              title="Re-analyser øta med rider_weight_kg fra localStorage (cg.profile.v1)"
            >
              {reAnalyzing ? "Re-analyserer…" : "Re-analyser med ny vekt"}
            </button>
          </div>
        </div>
      </header>

      {/* HOVEDINNHOLD */}
      <div className="space-y-6">
        {/* METRICS */}
        {metrics ? (
          <section className="border rounded-lg p-4 space-y-3">
            <h2 className="text-lg font-semibold">Analyse – Precision Watt</h2>

            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2 text-sm">
              <div>
                <dt className="text-slate-500">
                  Precision watt (snitt, fra analyze)
                </dt>
                <dd className="font-medium">{fmtW(precisionAvg)}</dd>
              </div>

              <div>
                <dt className="text-slate-500">Total watt</dt>
                <dd className="font-medium">
                  {fmtW(getNested(metrics, ["total_watt"]))}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Drag watt</dt>
                <dd className="font-medium">
                  {String(fmtW(getNested(metrics, ["drag_watt"])))}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Rolling watt</dt>
                <dd className="font-medium">
                  {String(fmtW(getNested(metrics, ["rolling_watt"])))}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Gravity watt</dt>
                <dd className="font-medium">
                  {String(fmtW(getNested(metrics, ["gravity_watt"])))}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Kalibrert mot wattmåler</dt>
                <dd className="font-medium">
                  {calibrated ? "Ja" : "Nei"}
                  {num(getNested(metrics, ["calibration_mae"])) !== null
                    ? ` (MAE ≈ ${num(getNested(metrics, ["calibration_mae"]))!.toFixed(
                        1
                      )} W)`
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

        {/* PROFIL */}
        {Boolean(hasProfile) && (
          <section className="border rounded-lg p-4 space-y-2 text-sm">
            <h2 className="text-lg font-semibold">Profil brukt i analysen</h2>

            <p className="text-slate-500">
              Versjon:{" "}
              <span className="font-mono">{String(profileVersionStr ?? "")}</span>
            </p>

            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1">
              <div>
                <dt className="text-slate-500">Totalvekt (rider + sykkel)</dt>
                <dd className="font-medium">{fmtKg(totalWeight)}</dd>
              </div>

              <div>
                <dt className="text-slate-500">CdA</dt>
                <dd className="font-medium">{String(cdaStr ?? "")}</dd>
              </div>

              <div>
                <dt className="text-slate-500">Crr</dt>
                <dd className="font-medium">{String(crrStr ?? "")}</dd>
              </div>

              <div>
                <dt className="text-slate-500">Enhet / device</dt>
                <dd className="font-medium">{String(deviceStr ?? "")}</dd>
              </div>
            </dl>
          </section>
        )}

        {/* VÆR */}
        {Boolean(weatherUsed) && (
          <section className="border rounded-lg p-4 space-y-2 text-sm">
            <h2 className="text-lg font-semibold">Vær brukt i analysen</h2>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1">
              <div>
                <dt className="text-slate-500">Vind</dt>
                <dd className="font-medium">
                  {fmtMs(getNested(weatherUsed, ["wind_ms"]))}{" "}
                  {num(getNested(weatherUsed, ["wind_dir_deg"])) !== null
                    ? `fra ${num(getNested(weatherUsed, ["wind_dir_deg"]))!.toFixed(
                        0
                      )}°`
                    : ""}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Temperatur</dt>
                <dd className="font-medium">
                  {fmtC(getNested(weatherUsed, ["air_temp_c"]))}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Lufttrykk</dt>
                <dd className="font-medium">
                  {fmtHpa(getNested(weatherUsed, ["air_pressure_hpa"]))}
                </dd>
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
