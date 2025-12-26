// frontend/src/pages/RidesPage.tsx
import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useSessionStore } from "../state/sessionStore";
import { formatStartTimeForUi } from "../lib/api";

const fmtDate = (iso?: string | null): string =>
  formatStartTimeForUi(iso ?? null);

const fmtNum = (n?: number | null, digits = 0): string =>
  typeof n === "number" && Number.isFinite(n) ? n.toFixed(digits) : "—";

const RidesPage: React.FC = () => {
  const navigate = useNavigate();
  const { sessionsList, loadingList, errorList, loadSessionsList } =
    useSessionStore();

  useEffect(() => {
    loadSessionsList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loadingList) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6">
        <div className="text-sm text-slate-500">Laster økter…</div>
      </div>
    );
  }

  if (errorList) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-3">
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm">
          {errorList}
        </div>
        <button
          type="button"
          onClick={() => loadSessionsList()}
          className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-slate-50"
        >
          Prøv igjen
        </button>
      </div>
    );
  }

  const rows = sessionsList ?? [];

  console.log(
  "[RidesPage] rows start_time snapshot",
  rows.map((r: any) => ({ id: r.session_id ?? r.ride_id, st: r.start_time })).slice(0, 20)
);

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-4">
      <header className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Økter</h1>
          <p className="text-sm text-slate-500">
            Viser {rows.length} økt(er) fra backend
          </p>
        </div>

        <button
          type="button"
          onClick={() => loadSessionsList()}
          className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-slate-50"
        >
          Oppdater
        </button>
      </header>

      {rows.length === 0 ? (
        <div className="text-sm text-slate-500">Ingen økter funnet.</div>
      ) : (
        <div className="space-y-3">
          {rows.map((s) => {
            const sid = s.session_id || s.ride_id; // robust fallback
            return (
              <div
                key={sid}
                className="border rounded-lg p-4 flex items-start justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="text-sm">
                    <span className="text-slate-500">Session ID:</span>{" "}
                    <span className="font-mono">{sid}</span>
                  </div>

                  <div className="text-sm">
                    <span className="text-slate-500">Dato:</span>{" "}
                    {fmtDate(s.start_time)}
                  </div>

                  <div className="text-sm">
                    <span className="text-slate-500">profil:</span>{" "}
                    {s.profile_label ?? "ukjent"}{" "}
                    <span className="text-slate-400">–</span>{" "}
                    <span className="text-slate-500">vær:</span>{" "}
                    {s.weather_source ?? "ukjent"}
                  </div>

                  <div className="text-sm">
                    <span className="text-slate-500">Precision Watt (snitt):</span>{" "}
                    <span className="font-medium">
                      {fmtNum(s.precision_watt_avg, 0)} W
                    </span>
                  </div>
                </div>

                <div className="flex flex-col items-end gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      navigate(`/session/${sid}`, { state: { from: "rides" } })
                    }
                    className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-slate-50"
                  >
                    Åpne økt →
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default RidesPage;
