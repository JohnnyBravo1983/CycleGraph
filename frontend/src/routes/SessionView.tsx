// frontend/src/routes/SessionView.tsx
import { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useSessionStore } from "../state/sessionStore";
import type { SessionReport } from "../types/session";
import SessionCard from "../components/SessionCard";
import { guessSampleLength, isShortSession } from "../lib/guards";
import { mockSessionShort } from "../mocks/mockSession";
import ErrorBanner from "../components/ErrorBanner";

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

export default function SessionView() {
  const params = useParams();
  const id = useMemo(() => params.id ?? "mock", [params.id]);

  const { session, loading, error, fetchSession } = useSessionStore();

  // 🔹 TRINN 4/5: kort-økt guard state
  const [sampleCount, setSampleCount] = useState<number>(0);
  const [shortSession, setShortSession] = useState<boolean>(false);

  // Ikke kall store ved dev-sti for kort økt
  useEffect(() => {
    if (id === "mock-short") return;
    fetchSession(id);
  }, [id, fetchSession]);

  // Bruk aktiv session, men override med mock-short i dev-sti
  const effectiveSession: SessionReport | null =
    id === "mock-short" ? mockSessionShort : session ?? null;

  // 🔹 Beregn samples + kort-økt når data endrer seg (inkl. mock-short)
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

  const hasError = !loading && !!error && id !== "mock-short";
  const friendlyMessage = error ? classifyErrorMessage(error) : "";

  return (
    <div className="page">
      {/* Header — ryddig, uten Env/Mode badges */}
      <div className="page-header">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Økt</h1>
        </div>
        <button
          onClick={() => id !== "mock-short" && fetchSession(id)}
          className={`btn ${
            id === "mock-short" ? "opacity-60 cursor-not-allowed" : ""
          }`}
          disabled={id === "mock-short"}
          title={
            id === "mock-short"
              ? "Dev-visning bruker lokal mock"
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
        <Link className="underline" to="/session/ABC123" title="Hent live-økt fra API">
          Live fra API
        </Link>
      </nav>

      {loading && id !== "mock-short" && (
        <div className="card">
          <Spinner />
        </div>
      )}

      {hasError && (
        <div className="mb-3">
          <ErrorBanner
            message={friendlyMessage}
            onRetry={() => fetchSession(id)}
          />
        </div>
      )}

      {effectiveSession && (
        <div className="grid gap-4">
          {/* Oppsummeringskort */}
          <SessionCard session={effectiveSession} />

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

      {!effectiveSession && !loading && !hasError && (
        <div className="card">Ingen data å vise.</div>
      )}

      {/* Diskré kildeinfo nederst (for utviklere), uten å spamme toppen */}
      <div className="mt-6 text-xs text-slate-400">
        Kilde:{" "}
        {id === "mock-short"
          ? "Eksempel (kort)"
          : id === "mock"
          ? "Eksempel"
          : "Live (API)"}
      </div>
    </div>
  );
}
