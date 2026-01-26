// frontend/src/routes/SessionsPage.tsx
import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useSessionStore } from "../state/sessionStore";
import type { SessionListItem } from "../types/session";
import { formatStartTimeForUi } from "../lib/api";
import { cgFetchJSON } from "../lib/cgFetch";


export const SessionsPage: React.FC = () => {
  const { sessionsList, loadingList, errorList, loadSessionsList } =
    useSessionStore();
  const navigate = useNavigate();

  // 🔍 Litt debug for å se hva som skjer hver render
  console.debug("[SessionsPage] render:", {
    count: sessionsList?.length ?? 0,
    loadingList,
    errorList,
    sessionsList,
  });

  useEffect(() => {
    console.debug("[SessionsPage] mount → henter økter...");

    // PATCH: sørg for at sessions-list alltid hentes via cgFetchJson (riktig base i prod + cookies)
    // Vi trigget dette i tillegg til store-load for å fange opp hvis store fortsatt bruker plain fetch.
    // Hvis store allerede er oppdatert til cgFetchJson kan du fjerne denne blokken senere.
    (async () => {
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const data = await cgFetchJSON<SessionListItem[]>("/api/sessions/list", { method: "GET" });  

        // Hvis store har en setter kan dere bruke den. Her gjør vi best-effort uten å endre store API:
        // Vi kaller loadSessionsList() etterpå slik at eksisterende flow beholdes.
        console.debug("[SessionsPage] cgFetchJson /api/sessions/list OK count=", data?.length ?? 0);
      } catch (e) {
        console.warn("[SessionsPage] cgFetchJson /api/sessions/list failed (fallback to store)", e);
      } finally {
        loadSessionsList();
      }
    })();
  }, [loadSessionsList]);

  const formatDate = (iso?: string | null): string =>
    formatStartTimeForUi(iso ?? null);

  const formatPrecision = (value?: number | null): string => {
    if (value == null || Number.isNaN(value)) return "—";
    return `${value.toFixed(0)} W`;
  };

  const handleOpen = (s: SessionListItem) => {
    const id = s.ride_id || s.session_id;
    if (!id) {
      console.warn(
        "[SessionsPage] Kan ikke navigere – mangler ride_id/session_id",
        s,
      );
      return;
    }
    console.debug("[SessionsPage] navigate → /sessions/", id);
    navigate(`/sessions/${id}`);
  };

  if (loadingList) {
    return (
      <div className="p-4">
        <h1 className="text-xl font-semibold mb-2">Økter</h1>
        <p>Laster økter fra backend…</p>
      </div>
    );
  }

  if (errorList) {
    return (
      <div className="p-4">
        <h1 className="text-xl font-semibold mb-2">Økter</h1>
        <p className="text-red-600 mb-4">
          Klarte ikke å laste økter: {errorList}
        </p>
        <button
          type="button"
          className="px-3 py-1 rounded bg-blue-600 text-white"
          onClick={() => loadSessionsList()}
        >
          Prøv igjen
        </button>
      </div>
    );
  }

  if (!sessionsList || sessionsList.length === 0) {
    return (
      <div className="p-4">
        <h1 className="text-xl font-semibold mb-2">
          Økter (fra /api/sessions/list)
        </h1>
        <p>Fant ingen økter i backend.</p>
      </div>
    );
  }

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-4">
        Økter (fra /api/sessions/list)
      </h1>

      <div className="space-y-3">
        {sessionsList.map((s) => {
          const key = s.session_id ?? s.ride_id;
          const idLabel = s.ride_id ?? s.session_id ?? "ukjent";
          const dateLabel = formatDate(s.start_time);
          const precisionLabel = formatPrecision(s.precision_watt_avg);
          const profileLabel = s.profile_label ?? "ukjent profil";
          const weatherLabel = s.weather_source ?? "ukjent værkilde";

          return (
            <div
              key={key}
              className="border rounded-lg px-4 py-3 bg-white shadow-sm flex flex-col sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="space-y-1">
                <div>
                  <span className="font-semibold">ID:</span> {idLabel}
                </div>
                <div>
                  <span className="font-semibold">Dato:</span> {dateLabel}
                </div>
                <div className="text-sm text-gray-600">
                  profil: {profileLabel} – vær: {weatherLabel}
                </div>
              </div>

              <div className="mt-3 sm:mt-0 flex items-center gap-4">
                <div className="text-right">
                  <div className="text-xs text-gray-500">
                    Precision Watt (snitt):
                  </div>
                  <div className="font-semibold">{precisionLabel}</div>
                </div>
                <button
                  type="button"
                  className="text-blue-600 underline text-sm"
                  onClick={() => handleOpen(s)}
                >
                  Åpne økt
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SessionsPage;
