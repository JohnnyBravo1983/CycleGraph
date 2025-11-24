import React, { useEffect, useMemo, useState, useRef } from "react";
import type { ComponentProps } from "react";
import { useParams, Link, useLocation } from "react-router-dom";
import { useSessionStore } from "../state/sessionStore";
import type { SessionReport } from "../types/session";
import SessionCard from "../components/SessionCard";
import { guessSampleLength, isShortSession } from "../lib/guards";
import { mockSessionShort } from "../mocks/mockSession";
import ErrorBanner from "../components/ErrorBanner";
import AnalysisPanel from "../components/AnalysisPanel";
import { mapAnalyzeToCard } from "../lib/mapAnalyzeToCard";
import type { Profile, AnalyzeResponse } from "../lib/schema";

import CalibrationGuide from "../components/CalibrationGuide";
// Lazy-load grafen (Performance boost)
const TrendsChart = React.lazy(() => import("../components/TrendsChart"));

// NEW: helpers for HR-only & modal
import { isHROnly as isHROnlyHelper, shouldShowCalibrationModal } from "../lib/state";

// --- Feature-flag for trend-modus (mock vs live) --------------------------
const USE_LIVE_TRENDS: boolean = (() => {
  const mode = import.meta.env.VITE_TRENDS_MODE;

  if (mode === "mock") return false;
  if (mode === "live") return true;

  // 🔁 Default: LIVE (backend /api/trend/summary.csv er på plass nå)
  return true;
})();

// Bruk nøyaktig typen som SessionCard forventer på `session`-propen
type SessionForCard = ComponentProps<typeof SessionCard>["session"];

/** DEV fetch-proxy guard (rewrite gamle stier → /api/...) */
function useDevFetchApiRewrite() {
  useEffect(() => {
    if (!import.meta.env.DEV) return;

    const backend =
      (import.meta as unknown as { env: Record<string, string | undefined> }).env
        .VITE_BACKEND_URL || "";

    const origFetch = window.fetch.bind(window);

    function rewrite(url: string): string {
      let u = url;

      try {
        const asUrl = new URL(url, window.location.origin);
        if (asUrl.origin === window.location.origin) {
          u = asUrl.pathname + asUrl.search;
        }
      } catch {
        // ignored
      }

      if (u.startsWith("/trends")) u = "/api" + u;
      if (u.startsWith("/session")) u = "/api" + u;
      if (u.startsWith("/stats")) u = "/api" + u;

      if (backend && u.startsWith("/api/")) {
        u = backend.replace(/\/+$/, "") + u;
      }
      return u;
    }

    window.fetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      if (typeof input === "string") return origFetch(rewrite(input), init);
      if (input instanceof URL) return origFetch(rewrite(input.toString()), init);

      try {
        const req = input as Request;
        const newUrl = rewrite(req.url);
        const requestInit: RequestInit = {
          method: req.method,
          headers: req.headers,
          body: req.body as BodyInit | null | undefined,
          mode: req.mode,
          credentials: req.credentials,
          cache: req.cache,
          redirect: req.redirect,
          referrer: req.referrer,
          referrerPolicy: req.referrerPolicy,
          signal: req.signal,
        };
        const integrity = (req as Partial<Request> & { integrity?: string }).integrity;
        if (integrity !== undefined) requestInit.integrity = integrity;
        const keepalive = (req as Partial<Request> & { keepalive?: boolean }).keepalive;
        if (typeof keepalive === "boolean") requestInit.keepalive = keepalive;

        return origFetch(newUrl, init ?? requestInit);
      } catch {
        return origFetch(input, init);
      }
    };

    return () => {
      window.fetch = origFetch;
    };
  }, []);
}

function Spinner() {
  return <div className="inline-block animate-pulse select-none">Laster…</div>;
}

function renderScalarOrList(
  v: SessionReport["wind_rel"] | SessionReport["v_rel"]
): string | number {
  if (Array.isArray(v)) {
    const head = v.slice(0, 6).join(", ");
    const tail = v.length > 6 ? ", …" : "";
    return `[${head}${tail}]`;
  }
  return v ?? "–";
}

/** ----------------------------------------------------------------------- */

function classifyErrorMessage(raw: string): string {
  if (/HTTP\s+404\b/.test(raw)) return "Ingen data å vise for denne økten.";
  if (/HTTP\s+5\d{2}\b/.test(raw)) return "Noe gikk galt. Prøv igjen senere.";
  if (/Tidsavbrudd|Failed to fetch|NetworkError|offline/i.test(raw)) {
    return "Kunne ikke hente data. Sjekk nettverk.";
  }
  if (/Unexpected token '<'|<!DOCTYPE/i.test(raw)) {
    return "Kunne ikke laste data (fikk HTML i stedet for JSON). Sjekk API-sti/proxy.";
  }
  return "Noe gikk galt. Prøv igjen.";
}

/** ────────────────────────────────────────────────────────────────────────
 *  Analysepanel-hjelpere (tydelige typer, ingen any)
 * ──────────────────────────────────────────────────────────────────────── */
type NumArray = number[];

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}
function isNumArray(v: unknown): v is NumArray {
  return Array.isArray(v) && v.every((x) => typeof x === "number" && Number.isFinite(x));
}
function getNumArrayProp(rec: unknown, key: string): NumArray | undefined {
  if (!isRecord(rec)) return undefined;
  const v = rec[key];
  return isNumArray(v) ? (v as NumArray) : undefined;
}
function getPrecisionCI(rec: unknown): { lower?: NumArray; upper?: NumArray } {
  if (!isRecord(rec)) return {};
  const lowerA = getNumArrayProp(rec, "pw_ci_lower");
  const upperA = getNumArrayProp(rec, "pw_ci_upper");
  if (lowerA && upperA) return { lower: lowerA, upper: upperA };
  const ciTuple = (rec as Record<string, unknown>)["precision_watt_ci"];
  if (Array.isArray(ciTuple) && ciTuple.length >= 2) {
    const l = isNumArray(ciTuple[0]) ? (ciTuple[0] as NumArray) : undefined;
    const u = isNumArray(ciTuple[1]) ? (ciTuple[1] as NumArray) : undefined;
    if (l || u) return { lower: l, upper: u };
  }
  if (isRecord(ciTuple)) {
    const l = getNumArrayProp(ciTuple, "lower");
    const u = getNumArrayProp(ciTuple, "upper");
    if (l || u) return { lower: l, upper: u };
  }
  return {};
}
function getBoolKey(rec: unknown, key: string): boolean | undefined {
  return isRecord(rec) && typeof rec[key] === "boolean" ? (rec[key] as boolean) : undefined;
}
function getStrKey(rec: unknown, key: string): string | undefined {
  return isRecord(rec) && typeof rec[key] === "string" ? (rec[key] as string) : undefined;
}
function getNestedStr(rec: unknown, parentKey: string, key: string): string | undefined {
  if (!isRecord(rec)) return undefined;
  const child = rec[parentKey];
  if (!isRecord(child)) return undefined;
  return typeof child[key] === "string" ? (child[key] as string) : undefined;
}
function getNestedBool(rec: unknown, parentKey: string, key: string): boolean | undefined {
  if (!isRecord(rec)) return undefined;
  const child = rec[parentKey];
  if (!isRecord(child)) return undefined;
  return typeof child[key] === "boolean" ? (child[key] as boolean) : undefined;
}
function getBackendSource(): "mock" | "api" {
  const env = (import.meta as unknown as { env: Record<string, string | undefined> }).env;
  return env.VITE_BACKEND_MODE === "mock" ? "mock" : "api";
}

function buildProfileFromAnalyze(ar: AnalyzeResponse): Profile {
  const used = ar.profile_used;

  return {
    rider_weight_kg: used.weight_kg,
    bike_weight_kg: 0, // TODO: kan justeres når vi har eksplisitt fordeling
    bike_type: used.bike_type,
    tire_width_mm: used.tire_width_mm,
    tire_quality: used.tire_quality,
    bike_name: null,
    cda: used.cda,
    crank_efficiency: used.crank_efficiency, // låst til 96% ifølge schema.ts
    profile_version: ar.profile_version,
    publish_to_strava: false,
  };
}
/** ──────────────────────────────────────────────────────────────────────── */

type LocalFixture = SessionReport & {
  precision_watt_ci?: { lower?: number[]; upper?: number[] };
};

function normalizeLegacy(s: SessionReport): SessionForCard {
  // Konverter watts til riktig format for SessionCard
  let normalizedWatts: number[] | null = null;

  if (Array.isArray(s.watts)) {
    normalizedWatts = s.watts;
  } else if (typeof s.watts === "number") {
    normalizedWatts = [s.watts];
  } else {
    normalizedWatts = null;
  }

  // Behold eksakt samme runtime-struktur, men gå via `unknown` for å slippe TS2352
  return {
    ...s,
    watts: normalizedWatts,
    sources: Array.isArray(s.sources) ? s.sources : [],
    precision_quality_hint: null,
    estimated_error_pct_range: null,
    precision_watt_ci: s.precision_watt_ci ?? null,
    CdA: null,
    crr_used: null,
    rider_weight: null,
    bike_weight: null,
    tire_width: null,
    bike_type: null,
    // publish_state fjernes her - SessionReport har ikke det
    publish_time: undefined,
  } as unknown as SessionForCard;
}

export default function SessionView() {
  useDevFetchApiRewrite();

  const params = useParams();
  const location = useLocation();
  const id = useMemo(() => params.id ?? "mock", [params.id]);

  const { session, loading, error, fetchSession } = useSessionStore();
  const { analyzeResult, analyzeSession, saveProfileAndReanalyze } = useSessionStore();
  const [sampleCount, setSampleCount] = useState<number>(0);
  const [shortSession, setShortSession] = useState<boolean>(false);

  const [local2h, setLocal2h] = useState<LocalFixture | null>(null);
  const [local2hLoading, setLocal2hLoading] = useState<boolean>(false);
  const [local2hError, setLocal2hError] = useState<string | null>(null);

  useEffect(() => {
    if (id === "mock-short" || id === "mock-2h") return;
    fetchSession(id);
  }, [id, fetchSession]);

  // Kjør analyze for alle ekte API-økter (ikke mock)
  useEffect(() => {
    if (id === "mock" || id === "mock-2h" || id === "mock-short") return;
    analyzeSession(id);
  }, [id, analyzeSession]);

  useEffect(() => {
    if (id !== "mock-2h") {
      setLocal2h(null);
      setLocal2hLoading(false);
      setLocal2hError(null);
      return;
    }
    setLocal2hLoading(true);
    setLocal2hError(null);
    fetch("/devdata/session_full_2h.json", { cache: "no-store" })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((json) => setLocal2h(json as LocalFixture))
      .catch((e) => setLocal2hError(String(e?.message || e)))
      .finally(() => setLocal2hLoading(false));
  }, [id]);

  const effectiveSession: SessionReport | null =
    id === "mock-short"
      ? mockSessionShort
      : id === "mock-2h"
      ? ((local2h as unknown) as SessionReport)
      : session ?? null;

  useEffect(() => {
    const s = effectiveSession;
    if (!s) {
      setSampleCount(0);
      setShortSession(false);
      return;
    }
    const n = guessSampleLength(s);
    setSampleCount(n);
    setShortSession(isShortSession(n, 30) || s.reason === "short_session");
  }, [effectiveSession]);

  const loadingNow = id === "mock-2h" ? local2hLoading : loading;
  const effectiveError = id === "mock-2h" ? local2hError : error;

  const hasError = !loadingNow && !!effectiveError && id !== "mock-short";
  const friendlyMessage = effectiveError ? classifyErrorMessage(effectiveError) : "";

  const wattsArr = useMemo<NumArray | undefined>(() => {
    const w = effectiveSession?.watts;
    return Array.isArray(w) && w.length > 0
      ? (w.filter((x) => Number.isFinite(x as number)) as number[])
      : undefined;
  }, [effectiveSession]);

  const hrArr = useMemo<NumArray | undefined>(() => {
    const h = getNumArrayProp(effectiveSession as unknown, "hr");
    return h && h.length > 0 ? h.filter((x) => Number.isFinite(x)) : undefined;
  }, [effectiveSession]);

  const { lower: ciLower, upper: ciUpper } = useMemo(
    () => getPrecisionCI(effectiveSession as unknown),
    [effectiveSession]
  );

  const showAnalysisPanel = useMemo(
    () => (wattsArr?.length ?? 0) > 0 || (hrArr?.length ?? 0) > 0,
    [wattsArr, hrArr]
  );

  const nForT = useMemo(
    () =>
      Math.max(
        wattsArr?.length ?? 0,
        hrArr?.length ?? 0,
        ciLower?.length ?? 0,
        ciUpper?.length ?? 0
      ),
    [wattsArr, hrArr, ciLower, ciUpper]
  );

  const tArr = useMemo(() => Array.from({ length: nForT }, (_, i) => i), [nForT]);

  const backendSource = useMemo(() => getBackendSource(), []);

  /** Toggle – styr grafen med VITE_TRENDS_MODE miljøvariabel */
  const useLiveTrends = USE_LIVE_TRENDS;
  const isMockForChart = !useLiveTrends;
  const sourceForChart = useLiveTrends ? "API" : "Mock";

  const qaLoggedRef = useRef(false);
  useEffect(() => {
    if (qaLoggedRef.current) return;
    qaLoggedRef.current = true;
    console.log(useLiveTrends ? "TrendsChart bruker LIVE-data" : "TrendsChart bruker MOCK-data");
  }, [useLiveTrends]);

  const calibrated = useMemo(
    () =>
      getBoolKey(effectiveSession, "calibrated") ??
      getNestedBool(effectiveSession, "session", "calibrated") ??
      false,
    [effectiveSession]
  );

  const statusRaw = useMemo(() => getStrKey(effectiveSession, "status"), [effectiveSession]);
  const status =
    statusRaw ?? (hrArr && !wattsArr ? "HR-only" : wattsArr && hrArr ? "FULL" : "LIMITED");

  const hrOnly = useMemo(
    () =>
      isHROnlyHelper({
        series: { hr: hrArr ?? [], watts: wattsArr ?? [] },
        flags: { hr_only: status === "HR-only" },
      }),
    [hrArr, wattsArr, status]
  );

  const sessionId = useMemo(
    () =>
      (getStrKey(effectiveSession, "id") ??
        getNestedStr(effectiveSession, "session", "id")) || id,
    [effectiveSession, id]
  );

  const derivedProfile = useMemo<Profile | null>(() => {
    if (!analyzeResult) return null;
    try {
      return buildProfileFromAnalyze(analyzeResult as AnalyzeResponse);
    } catch {
      return null;
    }
  }, [analyzeResult]);

  const panelSeries = useMemo(
    () => ({
      t: tArr,
      watts: wattsArr,
      hr: hrArr,
      precision_watt_ci: { lower: ciLower, upper: ciUpper },
      source: backendSource,
      calibrated,
      status,
      profile_cda: analyzeResult?.profile_used?.cda ?? null,
      profile_crr: analyzeResult?.profile_used?.crr ?? null,
      profile_crank_efficiency: analyzeResult?.profile_used?.crank_efficiency ?? null,
      profile_version: analyzeResult?.profile_version ?? null,
    }),
    [
      tArr,
      wattsArr,
      hrArr,
      ciLower,
      ciUpper,
      backendSource,
      calibrated,
      status,
      analyzeResult,
    ]
  );

  const mode: string = useMemo(
    () =>
      getStrKey(effectiveSession, "mode") ??
      getNestedStr(effectiveSession, "session", "mode") ??
      "outdoor",
    [effectiveSession]
  );

  const isFirstOutdoor = useMemo(
    () =>
      getNestedBool(effectiveSession, "meta", "is_first_outdoor") === true ||
      getNestedBool(effectiveSession, "context", "first_outdoor") === true ||
      false,
    [effectiveSession]
  );

  const allowCalibrationByHelper = useMemo(
    () =>
      shouldShowCalibrationModal({
        type: mode,
        calibrated,
        meta: { is_first_outdoor: isFirstOutdoor },
        series: { hr: hrArr ?? [], watts: wattsArr ?? [] },
        flags: { hr_only: hrOnly },
      }),
    [mode, calibrated, isFirstOutdoor, hrArr, wattsArr, hrOnly]
  );

  const forceCalibrate = useMemo(() => {
    const qs = new URLSearchParams(location.search);
    return qs.get("calibrate") === "1";
  }, [location.search]);

  const calibSeenKey = useMemo(() => `cg_calib_seen_${sessionId}`, [sessionId]);
  const alreadySeen = useMemo(() => {
    if (typeof window === "undefined") return false;
    try {
      return !!localStorage.getItem(calibSeenKey);
    } catch {
      // ignored
      return false;
    }
  }, [calibSeenKey]);

  const [showCalibration, setShowCalibration] = useState<boolean>(
    forceCalibrate || (allowCalibrationByHelper && !alreadySeen)
  );

  useEffect(() => {
    if (forceCalibrate) {
      setShowCalibration(true);
      return;
    }
    setShowCalibration(allowCalibrationByHelper && !alreadySeen);
  }, [forceCalibrate, allowCalibrationByHelper, alreadySeen, sessionId]);

  function handleCloseCalibration() {
    if (!forceCalibrate) {
      try {
        localStorage.setItem(calibSeenKey, "1");
      } catch {
        // ignored
      }
    }
    setShowCalibration(false);
  }

  function handleCalibrated() {
    try {
      localStorage.setItem(calibSeenKey, "1");
    } catch {
      // ignored
    }
    setShowCalibration(false);
  }

  // Velg data for kortet: analyzeResult → fallback til legacy session
  const sessionForCard = useMemo(
    () => {
      if (analyzeResult) {
        const mapped = mapAnalyzeToCard(analyzeResult);

        console.log("[SESSION VIEW] analyzeResult → mapped", { analyzeResult, mapped });

        if (!mapped) return null;

        // Konverter watts for analyzeResult også
        let normalizedWatts: number[] | null = null;

        if (Array.isArray(mapped.watts)) {
          normalizedWatts = mapped.watts;
        } else if (typeof mapped.watts === "number") {
          normalizedWatts = [mapped.watts];
        } else {
          normalizedWatts = null;
        }

        return {
          ...mapped,
          watts: normalizedWatts,
          sources: Array.isArray(mapped.sources) ? mapped.sources : [],
          precision_quality_hint: mapped.precision_quality_hint ?? null,
          estimated_error_pct_range: mapped.estimated_error_pct_range ?? null,
          precision_watt_ci: mapped.precision_watt_ci ?? null,
          CdA: mapped.CdA ?? null,
          crr_used: mapped.crr_used ?? null,
          rider_weight: mapped.rider_weight ?? null,
          bike_weight: mapped.bike_weight ?? null,
          tire_width: mapped.tire_width ?? null,
          bike_type: mapped.bike_type ?? null,
          // Midlertidig: vis badge som "published" for alle økter
          publish_state: "published",
        };
      }

      if (session) {
        const normalized = normalizeLegacy(session);

        console.log("[SESSION VIEW] legacy session → normalized", { session, normalized });

        return {
          ...normalized,
          // Midlertidig: vis badge som "published" for alle økter
          publish_state: "published",
        };
      }

      console.log("[SESSION VIEW] sessionForCard = null (ingen analyzeResult, ingen session)");
      return null;
    },
    [analyzeResult, session]
  ) as unknown as SessionForCard | null;

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Økt</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => id !== "mock-short" && id !== "mock-2h" && fetchSession(id)}
            className={`btn ${
              id === "mock-short" || id === "mock-2h" ? "opacity-60 cursor-not-allowed" : ""
            }`}
            disabled={id === "mock-short" || id === "mock-2h"}
            title={
              id === "mock-short"
                ? "Dev-visning bruker lokal mock (kort)"
                : id === "mock-2h"
                ? "Dev-visning bruker lokal 2h-fixture"
                : "Hent på nytt"
            }
          >
            Oppdater
          </button>

          <button
            type="button"
            className="btn"
            disabled={
              !derivedProfile ||
              id === "mock" ||
              id === "mock-short" ||
              id === "mock-2h"
            }
            onClick={() => {
              if (!derivedProfile) return;
              saveProfileAndReanalyze(sessionId, derivedProfile);
            }}
            title={
              derivedProfile
                ? "Lagre profil og kjør analysen på nytt med oppdatert profil."
                : "Profil er ikke tilgjengelig ennå."
            }
          >
            Lagre profil
          </button>

          <button
            type="button"
            className="btn"
            disabled={id === "mock" || id === "mock-short" || id === "mock-2h"}
            onClick={() => {
              if (id === "mock" || id === "mock-short" || id === "mock-2h") return;
              analyzeSession(sessionId);
            }}
            title={
              id === "mock" || id === "mock-short" || id === "mock-2h"
                ? "Analyseknapp er deaktivert for mock-økter."
                : "Kjør analyse på nytt for denne økten."
            }
          >
            Analyser økt
          </button>
        </div>
      </div>

      {/* Navigasjon */}
      <nav className="text-sm text-slate-600 mb-2">
        <span>Velg datasett: </span>
        <Link className="underline" to="/session/mock">
          Eksempel – Outdoor
        </Link>
        <span> · </span>
        <Link className="underline" to="/session/mock-short">
          Eksempel – Indoor (kort)
        </Link>
        <span> · </span>
        <Link className="underline" to="/session/mock-2h">
          Eksempel – 2h (stor)
        </Link>
        <span> · </span>
        <Link className="underline" to={`/session/${encodeURIComponent("local-mini")}`}>
          Live: local-mini (backend)
        </Link>
        {import.meta.env.DEV && (
          <>
            <span> · </span>
            <button
              className="underline text-emerald-700"
              onClick={() => setShowCalibration(true)}
            >
              Åpne kalibrering
            </button>
          </>
        )}
      </nav>

      {loadingNow && id !== "mock-short" && (
        <div className="card">
          <Spinner />
        </div>
      )}

      {hasError && (
        <div className="mb-3">
          <ErrorBanner
            message={friendlyMessage}
            onRetry={() => id !== "mock-2h" && fetchSession(id)}
          />
        </div>
      )}

      {sessionForCard && (
        <div className="grid gap-4">
          <SessionCard session={sessionForCard} />

          {showAnalysisPanel && <AnalysisPanel series={panelSeries} />}

          {/* Trender — lazy-loadet for performance */}
          <div className="card">
            <div className="k">Trender</div>
            <div className="mt-2">
              <React.Suspense
                fallback={
                  <div className="p-4 text-sm text-slate-500">Laster graf …</div>
                }
              >
                <TrendsChart
                  key={sessionId}
                  sessionId={sessionId}
                  isMock={isMockForChart}
                  series={{ t: tArr, watts: wattsArr, hr: hrArr }}
                  calibrated={calibrated}
                  source={sourceForChart}
                  hrOnly={hrOnly}
                />
              </React.Suspense>
            </div>
          </div>

          {shortSession && (
            <div className="mt-0 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-amber-900">
              <div className="font-medium">Kort økt – viser begrenset visning</div>
              <div className="text-sm opacity-80">
                Samples: {sampleCount} (krever ≥ 30 for full analyse)
              </div>
            </div>
          )}

          {/* Vis disse detaljene bare hvis effectiveSession er tilgjengelig */}
          {effectiveSession && (
            <>
              <div className="card">
                <div className="k">schema_version</div>
                <div className="mono">{effectiveSession.schema_version}</div>
              </div>

              <div className="card">
                <div className="k">watt-data</div>
                <div className="mono text-sm break-words">
                  {Array.isArray(effectiveSession.watts) 
                    ? `[${effectiveSession.watts.slice(0, 10).join(", ")}${effectiveSession.watts.length > 10 ? ", …" : ""}]`
                    : effectiveSession.watts ?? "—"}
                </div>
              </div>

              <div className="card grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="k">wind_rel</div>
                  <div className="mono text-sm break-words">
                    {renderScalarOrList(effectiveSession.wind_rel)}
                  </div>
                </div>
                <div>
                  <div className="k">v_rel</div>
                  <div className="mono text-sm break-words">
                    {renderScalarOrList(effectiveSession.v_rel)}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {!effectiveSession && !sessionForCard && !loadingNow && !hasError && (
        <div className="card">Ingen data å vise.</div>
      )}

      <div className="mt-6 text-xs text-slate-400">
        Kilde:{" "}
        {id === "mock-short"
          ? "Eksempel (kort)"
          : id === "mock-2h"
          ? "Eksempel (2h stor)"
          : id === "mock"
          ? "Eksempel"
          : "Live (API)"}{" "}
        {import.meta.env.DEV && (
          <>
            — Tips: legg til <code>?calibrate=1</code> i URL.
          </>
        )}
      </div>

      {showCalibration && (
        <CalibrationGuide
          sessionId={sessionId}
          isOpen={showCalibration}
          onClose={handleCloseCalibration}
          onCalibrated={handleCalibrated}
          isMock={isMockForChart}
        />
      )}
    </div>
  );
}
