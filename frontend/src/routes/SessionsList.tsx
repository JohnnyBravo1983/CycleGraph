import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useSessionStore } from "../state/sessionStore";
import type { SessionInfo } from "../types/session";

function formatDate(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso ?? "";
  return d.toLocaleString();
}

function sessionLabel(session: SessionInfo): string {
  if (session.label) return session.label;
  if (session.ride_id) return `Ride ${session.ride_id}`;
  if (session.profile_version) return session.profile_version;
  return session.session_id || "Ukjent økt";
}

function SessionsList() {
  const { sessions, sessionsLoading, sessionsError, fetchSessionsList } =
    useSessionStore((state) => ({
      sessions: state.sessions,
      sessionsLoading: state.sessionsLoading,
      sessionsError: state.sessionsError,
      fetchSessionsList: state.fetchSessionsList,
    }));

  useEffect(() => {
    void fetchSessionsList();
  }, [fetchSessionsList]);

  return (
    <main className="max-w-3xl mx-auto px-4 py-8 space-y-4">
      <header className="flex items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Økter</h1>
        <span className="text-sm text-gray-500">
          Klikk på en økt for å åpne detaljer
        </span>
      </header>

      {sessionsLoading && (
        <p data-testid="sessions-loading" className="text-sm text-gray-500">
          Laster økter …
        </p>
      )}

      {sessionsError && !sessionsLoading && (
        <p
          data-testid="sessions-error"
          className="text-sm text-red-600"
          role="alert"
        >
          Klarte ikke å hente økter: {sessionsError}
        </p>
      )}

      {!sessionsLoading &&
        !sessionsError &&
        (!sessions || sessions.length === 0) && (
          <p data-testid="sessions-empty" className="text-sm text-gray-500">
            Ingen økter tilgjengelig ennå. Kjør en analyse først.
          </p>
        )}

      {sessions && sessions.length > 0 && (
        <ul className="space-y-2" data-testid="sessions-list">
          {sessions.map((s) => {
            const label = sessionLabel(s);
            const hasSessionId = !!s.session_id;

            const content = (
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="font-medium">{label}</div>
                  {s.session_id && s.session_id !== label && (
                    <div className="text-xs text-gray-500">{s.session_id}</div>
                  )}
                  {s.weather_source && (
                    <div className="text-[11px] text-gray-500">
                      Værkilde: {s.weather_source}
                    </div>
                  )}
                </div>
                <div className="text-right text-xs text-gray-500">
                  {s.mode && (
                    <div className="uppercase tracking-wide">
                      {s.mode === "indoor" ? "INNENDØRS" : "UTENDØRS"}
                    </div>
                  )}
                  {s.started_at && <div>{formatDate(s.started_at)}</div>}
                  {s.profile_version && (
                    <div className="text-[10px] text-gray-400">
                      {s.profile_version}
                    </div>
                  )}
                </div>
              </div>
            );

            return (
              <li key={s.session_id || `${s.profile_version ?? "no-id"}-${Math.random()}`}>
                {hasSessionId ? (
                  <Link
                    to={`/session/${encodeURIComponent(s.session_id)}`}
                    className="block rounded-lg border border-gray-200 px-4 py-3 hover:bg-gray-50 transition-colors"
                  >
                    {content}
                  </Link>
                ) : (
                  <div
                    className="block rounded-lg border border-gray-200 px-4 py-3 bg-gray-50/70 text-gray-500 cursor-not-allowed"
                    aria-disabled="true"
                    title="Denne raden mangler session_id i backend og kan ikke åpnes ennå."
                  >
                    {content}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}

export default SessionsList;
export { SessionsList };