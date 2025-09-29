import { useEffect } from "react";
import { useSessionStore } from "../state/sessionStore";
import type { SessionReport } from "../types/session";

// Enkle UI-snutter (inline for å slippe ekstra filer)
function ModeBadge() {
  const isMock = import.meta.env.VITE_USE_MOCK !== "0";
  return (
    <span
      title={isMock ? "Data fra mockSession" : "Data fra backend"}
      className="text-[11px] px-2 py-1 rounded-full border"
    >
      MODE: {isMock ? "MOCK" : "LIVE"}
    </span>
  );
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

export default function SessionView() {
  const { session, loading, error, fetchSession } = useSessionStore();

  useEffect(() => {
    // Hent en demo-økt ved mount
    fetchSession("demo");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // fetchSession er stabil i vår Zustand-implementasjon

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Økt</h1>
          <ModeBadge />
        </div>
        <button
          onClick={() => fetchSession("demo")}
          className="px-3 py-2 rounded-2xl shadow hover:shadow-md border"
        >
          Oppdater
        </button>
      </div>

      {loading && (
        <div className="rounded-2xl border p-4">
          <Spinner />
        </div>
      )}

      {!loading && error && (
        <div className="rounded-2xl border p-4 text-red-700">
          Kunne ikke hente økt: <span className="font-mono">{error}</span>
        </div>
      )}

      {!loading && !error && session && (
        <div className="grid gap-4">
          <div className="rounded-2xl border p-4">
            <div className="text-sm text-gray-500">schema_version</div>
            <div className="font-mono">{session.schema_version}</div>
          </div>

          <div className="rounded-2xl border p-4 grid grid-cols-2 gap-4">
            <div>
              <div className="text-sm text-gray-500">avg_hr</div>
              <div className="font-mono">{session.avg_hr ?? "–"}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">calibrated</div>
              <div className="font-mono">{String(session.calibrated)}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">status</div>
              <div className="font-mono">{session.status}</div>
            </div>
          </div>

          <div className="rounded-2xl border p-4">
            <div className="text-sm text-gray-500">watt-data</div>
            {session.watts && session.watts.length > 0 ? (
              <div className="font-mono text-sm break-words">
                [{session.watts.slice(0, 10).join(", ")}
                {session.watts.length > 10 ? ", …" : ""}]
              </div>
            ) : (
              <div className="italic text-gray-600">
                HR-only: ingen watt i denne økten
              </div>
            )}
          </div>

          <div className="rounded-2xl border p-4 grid grid-cols-2 gap-4">
            <div>
              <div className="text-sm text-gray-500">wind_rel</div>
              <div className="font-mono text-sm break-words">
                {renderScalarOrList(session.wind_rel)}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-500">v_rel</div>
              <div className="font-mono text-sm break-words">
                {renderScalarOrList(session.v_rel)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}