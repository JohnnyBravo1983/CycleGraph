// frontend/src/routes/SessionView.tsx
import { useEffect, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { useSessionStore } from "../state/sessionStore";
import type { SessionReport } from "../types/session";
import ModeBadge from "../components/ModeBadge";
import SessionCard from "../components/SessionCard";

function Spinner() {
  return <div className="inline-block animate-pulse select-none">Laster…</div>;
}

function EnvBadge({ source }: { source: "mock" | "live" | null }) {
  const tone =
    source === "live"
      ? "bg-blue-100 text-blue-800"
      : source === "mock"
      ? "bg-gray-100 text-gray-800"
      : "bg-slate-100 text-slate-800";
  const label = source === "live" ? "Live" : source === "mock" ? "Mock" : "—";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${tone}`}
    >
      {label}
    </span>
  );
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

export default function SessionView() {
  const params = useParams();
  const id = useMemo(() => params.id ?? "mock", [params.id]);

  const { session, source, loading, error, fetchSession } = useSessionStore();

  useEffect(() => {
    fetchSession(id);
  }, [id, fetchSession]);

  return (
    <div className="page">
      <div className="page-header">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Økt</h1>
          <EnvBadge source={source} />
          {session && <ModeBadge />}
        </div>
        <button onClick={() => fetchSession(id)} className="btn">
          Oppdater
        </button>
      </div>

      <nav className="text-sm text-slate-600 mb-2">
        <span>Hopp til: </span>
        <Link className="underline" to="/session/mock">
          mock
        </Link>
        <span> · </span>
        <Link className="underline" to="/session/ABC123">
          live eksempel
        </Link>
      </nav>

      {loading && (
        <div className="card">
          <Spinner />
        </div>
      )}

      {!loading && error && (
        <div className="card text-red-700">
          Kunne ikke hente økt: <span className="mono">{error}</span>
        </div>
      )}

      {!loading && !error && session && (
        <div className="grid gap-4">
          {/* Oppsummeringskort */}
          <SessionCard session={session} />

          {/* Ekstra: schema_version */}
          <div className="card">
            <div className="k">schema_version</div>
            <div className="mono">{session.schema_version}</div>
          </div>

          {/* Ekstra: watt-data (rå visning) */}
          <div className="card">
            <div className="k">watt-data</div>
            {hasWattsValue(session.watts) ? (
              <div className="mono text-sm break-words">
                {wattsPreview(session.watts)}
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
                {renderScalarOrList(session.wind_rel)}
              </div>
            </div>
            <div>
              <div className="k">v_rel</div>
              <div className="mono text-sm break-words">
                {renderScalarOrList(session.v_rel)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
