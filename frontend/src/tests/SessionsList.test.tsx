// frontend/src/routes/SessionsList.tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useSessionStore } from "../state/sessionStore";
import type { SessionInfo } from "../types/session";

function formatDateTime(iso?: string | null): string {
  if (!iso) return "Ukjent tidspunkt";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function formatMode(mode?: SessionInfo["mode"] | null): string {
  if (!mode) return "ukjent";
  if (mode === "indoor") return "innendørs";
  if (mode === "outdoor") return "utendørs";
  return mode;
}

export default function SessionsList() {
  const [showMocks, setShowMocks] = useState(false);

  const sessions = useSessionStore((s) => s.sessions ?? []);
  const sessionsLoading = useSessionStore((s) => s.sessionsLoading);
  const sessionsError = useSessionStore((s) => s.sessionsError);
  const fetchSessionsList = useSessionStore((s) => s.fetchSessionsList);

  useEffect(() => {
    void fetchSessionsList();
  }, [fetchSessionsList]);

  const visibleSessions = sessions.filter((s) => {
    if (showMocks) return true;
    const id = s.session_id ?? "";
    // Skjul mock-økter og local-mini som default
    return !id.startsWith("mock-") && id !== "local-mini";
  });

  return (
    <div className="max-w-5xl mx-auto px-6 py-6 space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Mine økter</h1>
        <label className="flex items-center gap-2 text-xs text-gray-600">
          <input
            type="checkbox"
            className="rounded border-gray-300"
            checked={showMocks}
            onChange={(e) => setShowMocks(e.target.checked)}
          />
          Vis mock-økter
        </label>
      </header>

      {sessionsLoading && <p>Laster økter…</p>}
      {sessionsError && <p className="text-red-600">{sessionsError}</p>}

      {!sessionsLoading && !sessionsError && visibleSessions.length === 0 && (
        <p>Ingen økter funnet ennå.</p>
      )}

      {!sessionsLoading && !sessionsError && visibleSessions.length > 0 && (
        <ul className="divide-y border rounded-xl bg-white">
          {visibleSessions.map((s) => (
            <li
              key={s.session_id}
              className="px-4 py-3 flex items-center justify-between gap-4"
            >
              <div className="space-y-1">
                <Link
                  to={`/session/${s.session_id}`}
                  className="font-medium text-blue-700 hover:underline"
                >
                  {s.session_id}
                </Link>
                <div className="text-sm text-gray-600">
                  <span>{formatDateTime(s.started_at)}</span>
                  {" · "}
                  <span>{formatMode(s.mode)}</span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
