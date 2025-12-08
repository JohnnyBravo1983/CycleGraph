// frontend/src/routes/SessionsPage.tsx
import React, { useEffect } from "react";
import { useSessionStore } from "../state/sessionStore";

// Lokal type for hva vi forventer at én økt inneholder
type SessionListItem = {
  id: string;
  start_time?: string;
  precision_watt_avg?: number | null;
  avg_power?: number | null;
};

export const SessionsPage: React.FC = () => {
  // TS-triks: cast via unknown først, så til vår lokale shape.
  const { sessionsList, loadingList, errorList, loadSessionsList } =
    (useSessionStore() as unknown) as {
      sessionsList: SessionListItem[] | null;
      loadingList: boolean;
      errorList: string | null;
      loadSessionsList: () => void;
    };

  useEffect(() => {
    // Last økter når siden åpnes
    loadSessionsList();
  }, [loadSessionsList]);

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
        <p className="text-red-600">Feil ved henting av økter: {errorList}</p>
      </div>
    );
  }

  if (!sessionsList || sessionsList.length === 0) {
    return (
      <div className="p-4">
        <h1 className="text-xl font-semibold mb-2">Økter</h1>
        <p>Ingen økter funnet i summary.csv.</p>
      </div>
    );
  }

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-4">Økter (fra summary.csv)</h1>

      <ul className="space-y-2">
        {sessionsList.map((s: SessionListItem) => {
          // Bruk precision_watt_avg som hovedkilde,
          // men fall back til avg_power hvis den mot formodning er satt.
          const pw =
            s.precision_watt_avg != null
              ? s.precision_watt_avg
              : s.avg_power != null
              ? s.avg_power
              : null;

          return (
            <li
              key={s.id}
              className="border rounded-lg p-3 flex flex-col md:flex-row md:items-center md:justify-between"
            >
              <div>
                <div className="font-mono text-sm text-gray-700">
                  ID: {s.id}
                </div>
                <div className="text-sm text-gray-500">
                  Dato: {s.start_time || "ukjent"}
                </div>
              </div>

              <div className="mt-1 md:mt-0 text-sm text-gray-700">
                Precision Watt (snitt):{" "}
                {pw != null ? `${Math.round(pw)} W` : "—"}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
};

export default SessionsPage;
