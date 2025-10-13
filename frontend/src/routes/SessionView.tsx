import { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useSessionStore } from "../state/sessionStore";
import type { SessionReport } from "../types/session";
import SessionCard from "../components/SessionCard";
import { guessSampleLength, isShortSession } from "../lib/guards";
import { mockSessionShort } from "../mocks/mockSession";
import ErrorBanner from "../components/ErrorBanner";
import AnalysisPanel from "../components/AnalysisPanel";

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

function hasWattsValue(w: SessionReport["watts"]): boolean {
  if (typeof w === "number") return Number.isFinite(w);
  if (Array.isArray(w)) return w.some((x) => Number.isFinite(x as number));
  return false;
}

function wattsPreview(w: SessionReport["watts"]): string {
  if (typeof w === "number" && Number.isFinite(w)) {
    return `${Math.round(w)} W`;
  }
  if (Array.isArray(w) && w.length > 0) {
    const slice = w.slice(0, 10);
    const body = slice
      .map((x) => (Number.isFinite(x as number) ? x : "NaN"))
      .join(", ");
    const tail = w.length > 10 ? ", …" : "";
    return `[${body}${tail}]`;
  }
  return "—";
}

/** ---- DEV-sanity helpers (no-any) -------------------------------------- */
type PrecisionFields = {
  precision_watt?: unknown;
  precision_watt_ci?: unknown;
};

function getDevPrecisionCounts(
  s: SessionReport
): { pw: number; ci: number } | null {
  const pf: PrecisionFields = s as unknown as PrecisionFields;

  const pwArr = Array.isArray(pf.precision_watt)
    ? (pf.precision_watt as unknown[])
    : null;
  if (!pwArr) return null;

  const ciArr = Array.isArray(pf.precision_watt_ci)
    ? (pf.precision_watt_ci as unknown[])
    : [];

  return { pw: pwArr.length, ci: ciArr.length };
}
/** ----------------------------------------------------------------------- */

/** Klassifiser rå feiltekst til bruker-vennlige meldinger */
function classifyErrorMessage(raw: string): string {
  if (/HTTP\s+404\b/.test(raw)) return "Ingen data å vise for denne økten.";
  if (/HTTP\s+5\d{2}\b/.test(raw)) return "Noe gikk galt. Prøv igjen senere.";
  if (/Tidsavbrudd|Failed to fetch|NetworkError|offline/i.test(raw)) {
    return "Kunne ikke hente data. Sjekk nettverk.";
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
  // Direkte pw_ci_lower/pw_ci_upper på rapporten
  const lowerA = getNumArrayProp(rec, "pw_ci_lower");
  const upperA = getNumArrayProp(rec, "pw_ci_upper");
  if (lowerA && upperA) return { lower: lowerA, upper: upperA };

  // precision_watt_ci som tuple [lower, upper]
  const ciTuple = (rec as Record<string, unknown>)["precision_watt_ci"];
  if (Array.isArray(ciTuple) && ciTuple.length >= 2) {
    const l = isNumArray(ciTuple[0]) ? (ciTuple[0] as NumArray) : undefined;
    const u = isNumArray(ciTuple[1]) ? (ciTuple[1] as NumArray) : undefined;
    if (l || u) return { lower: l, upper: u };
  }

  // precision_watt_ci som objekt { lower, upper }
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

function getBackendSource(): "mock" | "api" {
  const env = (import.meta as unknown as { env: Record<string, string | undefined> }).env;
  return env.VITE_BACKEND_MODE === "mock" ? "mock" : "api";
}
/** ──────────────────────────────────────────────────────────────────────── */

/** Lokalt 2h-fixture (mock-2h) */
type LocalFixture = SessionReport & {
  precision_watt_ci?: { lower?: number[]; upper?: number[] };
};

export default function SessionView() {
  const params = useParams();
  const id = useMemo(() => params.id ?? "mock", [params.id]);

  const { session, loading, error, fetchSession } = useSessionStore();

  // 🔹 TRINN 4/5: kort-økt guard state
  const [sampleCount, setSampleCount] = useState<number>(0);
  const [shortSession, setShortSession] = useState<boolean>(false);

  // Lokalt 2h (mock-2h)
  const [local2h, setLocal2h] = useState<LocalFixture | null>(null);
  const [local2hLoading, setLocal2hLoading] = useState<boolean>(false);
  const [local2hError, setLocal2hError] = useState<string | null>(null);

  // Ikke kall store ved dev-stier for mock-short og mock-2h
  useEffect(() => {
    if (id === "mock-short" || id === "mock-2h") return;
    fetchSession(id);
  }, [id, fetchSession]);

  // Last lokal 2h-fixture når id === mock-2h
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
      .then((json) => {
        setLocal2h(json as LocalFixture);
      })
      .catch((e) => setLocal2hError(String(e?.message || e)))
      .finally(() => setLocal2hLoading(false));
  }, [id]);

  // Bruk aktiv session, men override med mock-varianter i dev-stier
  const effectiveSession: SessionReport | null =
    id === "mock-short" ? mockSessionShort :
    id === "mock-2h" ? (local2h as unknown as SessionReport) :
    session ?? null;

  // 🔹 Beregn samples + kort-økt når data endrer seg (inkl. mock-short/2h)
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

  const devCounts =
    import.meta.env.DEV && effectiveSession
      ? getDevPrecisionCounts(effectiveSession)
      : null;

  // Samlet loading/error (inkluder lokal 2h)
  const loadingNow = id === "mock-2h" ? local2hLoading : loading;
  const effectiveError = id === "mock-2h" ? local2hError : error;

  const hasError = !loadingNow && !!effectiveError && id !== "mock-short";
  const friendlyMessage = effectiveError ? classifyErrorMessage(effectiveError) : "";

  /** ── For Analysepanel: trekk ut arrays og CI, og bygg series-prop ── */
  const wattsArr = useMemo<NumArray | undefined>(() => {
    const w = effectiveSession?.watts;
    return Array.isArray(w) && w.length > 0
      ? (w.filter((x) => Number.isFinite(x as number)) as number[])
      : undefined;
  }, [effectiveSession]);

  // Hent hr via helper (feltet er valgfritt i SessionReport)
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

  const source = useMemo(() => getBackendSource(), []);
  const calibrated = useMemo(
    () => getBoolKey(effectiveSession, "calibrated") ?? false,
    [effectiveSession]
  );
  const statusRaw = useMemo(
    () => getStrKey(effectiveSession, "status"),
    [effectiveSession]
  );
  const status =
    statusRaw ??
    ((hrArr && !wattsArr) ? "HR-only" : (wattsArr && hrArr) ? "FULL" : "LIMITED");

  const panelSeries = useMemo(
    () => ({
      t: tArr,
      watts: wattsArr,
      hr: hrArr,
      precision_watt_ci: { lower: ciLower, upper: ciUpper },
      source,
      calibrated,
      status,
    }),
    [tArr, wattsArr, hrArr, ciLower, ciUpper, source, calibrated, status]
  );

  return (
    <div className="page">
      {/* Header — ryddig, uten Env/Mode badges */}
      <div className="page-header">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Økt</h1>
        </div>
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
      </div>

      {/* Navigasjon — tydelig skille mellom eksempler og live */}
      <nav className="text-sm text-slate-600 mb-2">
        <span>Velg datasett: </span>
        <Link className="underline" to="/session/mock" title="Vis eksempeløkt (outdoor)">
          Eksempel – Outdoor
        </Link>
        <span> · </span>
        <Link className="underline" to="/session/mock-short" title="Vis kort eksempeløkt (indoor)">
          Eksempel – Indoor (kort)
        </Link>
        <span> · </span>
        <Link className="underline" to="/session/mock-2h" title="Vis 2 timer (stor)">
          Eksempel – 2h (stor)
        </Link>
        <span> · </span>
        <Link className="underline" to="/session/ABC123" title="Hent live-økt fra API">
          Live fra API
        </Link>
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

      {effectiveSession && (
        <div className="grid gap-4">
          {/* Oppsummeringskort */}
          <SessionCard session={effectiveSession} />

          {/* Analysepanel (kun hvis vi har minst én serie som array) */}
          {showAnalysisPanel && (
            <AnalysisPanel series={panelSeries} />
          )}

          {/* 🔹 DEV-sanity for Precision Watt (kun i dev, lint-safe) */}
          {devCounts && (
            <div className="mt-0 rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-slate-800 text-xs">
              <span className="mr-2 rounded bg-slate-200 px-2 py-0.5 font-mono">
                DEV
              </span>
              <span className="mr-4">PW samples: {devCounts.pw}</span>
              <span>CI: {devCounts.ci}</span>
            </div>
          )}

          {/* 🔹 kort-økt info-kort */}
          {shortSession && (
            <div className="mt-0 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-amber-900">
              <div className="font-medium">Kort økt – viser begrenset visning</div>
              <div className="text-sm opacity-80">
                Samples: {sampleCount} (krever ≥ 30 for full analyse)
              </div>
            </div>
          )}

          {/* Ekstra: schema_version */}
          <div className="card">
            <div className="k">schema_version</div>
            <div className="mono">{effectiveSession.schema_version}</div>
          </div>

          {/* Ekstra: watt-data (rå visning) */}
          <div className="card">
            <div className="k">watt-data</div>
            {hasWattsValue(effectiveSession.watts) ? (
              <div className="mono text-sm break-words">
                {wattsPreview(effectiveSession.watts)}
              </div>
            ) : (
              <div className="italic text-gray-600">
                HR-only: ingen watt i denne økten
              </div>
            )}
          </div>

          {/* Ekstra: wind_rel / v_rel */}
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
        </div>
      )}

      {!effectiveSession && !loadingNow && !hasError && (
        <div className="card">Ingen data å vise.</div>
      )}

      {/* Diskré kildeinfo nederst (for utviklere), uten å spamme toppen */}
      <div className="mt-6 text-xs text-slate-400">
        Kilde:{" "}
        {id === "mock-short"
          ? "Eksempel (kort)"
          : id === "mock-2h"
          ? "Eksempel (2h stor)"
          : id === "mock"
          ? "Eksempel"
          : "Live (API)"}
      </div>
    </div>
  );
}
