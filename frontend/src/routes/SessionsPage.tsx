import React, { useEffect } from "react";
import { useSessionStore } from "../state/sessionStore";
import { useNavigate } from "react-router-dom";

export const SessionsPage: React.FC = () => {
  const { sessionsList, loadingList, errorList, loadSessionsList } =
    useSessionStore();
  const navigate = useNavigate();

  useEffect(() => {
    loadSessionsList();
  }, [loadSessionsList]);

  const formatDate = (iso?: string | null): string => {
    if (!iso) return "ukjent";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "ukjent";
    return d.toLocaleString("nb-NO", {
      dateStyle: "short",
      timeStyle: "short",
    });
  };

  const formatPrecisionWatt = (value?: number | null): string => {
    if (typeof value !== "number" || Number.isNaN(value)) return "—";
    return `${Math.round(value)} W`;
  };

  if (loadingList) {
    return (
      <div className="p-4">
        <h1 className="text-xl font-semibold mb-2">
          Økter (fra /api/sessions/list)
        </h1>
        <p>Laster økter fra backend…</p>
      </div>
    );
  }

  if (errorList) {
    return (
      <div className="p-4">
        <h1 className="text-xl font-semibold mb-2">
          Økter (fra /api/sessions/list)
        </h1>
        <p className="text-red-600">Feil ved henting av økter: {errorList}</p>
      </div>
    );
  }

  if (!sessionsList || sessionsList.length === 0) {
    return (
      <div className="p-4">
        <h1 className="text-xl font-semibold mb-2">
          Økter (fra /api/sessions/list)
        </h1>
        <p>Fant ingen økter.</p>
      </div>
    );
  }

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-4">
        Økter (fra /api/sessions/list)
      </h1>

      <div className="space-y-3">
        {sessionsList.map((s) => (
          <div
            key={s.id}
            className="border rounded-lg p-3 flex flex-col gap-1 bg-white shadow-sm"
          >
            <div className="flex justify-between items-center">
              <div>
                <p className="font-medium">ID: {s.id}</p>
                <p>
                  Dato: <span>{formatDate(s.start_time)}</span>
                </p>
                {s.profile_label && (
                  <p className="text-sm text-gray-600">
                    profil: {s.profile_label}
                  </p>
                )}
                {typeof s.distance_km === "number" && (
                  <p className="text-sm text-gray-600">
                    Distanse: {s.distance_km.toFixed(1)} km
                  </p>
                )}
              </div>

              <div className="text-right">
                <p>Precision Watt (snitt):</p>
                <p className="font-semibold">
                  {formatPrecisionWatt(s.precision_watt_avg)}
                </p>
                <button
                  className="mt-2 text-blue-600 underline"
                  onClick={() => navigate(`/session/${s.id}`)}
                >
                  Åpne økt
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SessionsPage;
