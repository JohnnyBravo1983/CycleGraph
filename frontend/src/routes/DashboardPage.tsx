// frontend/src/routes/DashboardPage.tsx
import { StravaImportCard } from "../components/StravaImportCard";
import { AccountStatus } from "../components/AccountStatus";
import { Link } from "react-router-dom";

import { isDemoMode } from "../demo/demoMode";
import { demoDashboard } from "../demo/demoData";

export default function DashboardPage() {
  const demo = isDemoMode();

  return (
    <div className="flex flex-col gap-8">
      {/* DEMO: top card */}
      {demo && (
        <section className="border border-amber-200 bg-amber-50 rounded-2xl p-4">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <div className="text-sm text-amber-900">
                🎬 <span className="font-semibold">Demo Mode</span> – Viewing{" "}
                <span className="font-semibold">Johnny</span>’s training data
              </div>
              <div className="text-xs text-amber-900/80 mt-1">
                Demo-data er hardcoded nå (ingen backend nødvendig).
              </div>
            </div>

            <div className="text-right">
              <div className="text-xs text-amber-900/80">This week</div>
              <div className="text-sm font-semibold text-amber-900">
                {demoDashboard.weekSummary.rides} rides · {demoDashboard.weekSummary.hours} h ·{" "}
                {demoDashboard.weekSummary.distanceKm} km · {demoDashboard.weekSummary.avgPw} W
              </div>
            </div>
          </div>

          <div className="mt-4">
            <div className="text-sm font-semibold text-amber-900 mb-2">Recent demo rides</div>
            <div className="flex flex-col gap-2">
              {demoDashboard.recentRides.map((r) => (
                <Link
                  key={r.id}
                  to={`/session/${r.id}`}
                  className="px-3 py-2 rounded-xl border border-amber-200 bg-white hover:bg-amber-50 flex items-center justify-between gap-4"
                >
                  <div className="min-w-0">
                    <div className="font-medium text-slate-900 truncate">{r.title}</div>
                    <div className="text-xs text-slate-600">
                      {new Date(r.date).toLocaleString()}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-sm font-semibold">{r.precisionWattAvg} W</div>
                    <div className="text-xs text-slate-600">
                      {Math.round(r.distanceKm)} km · {r.durationMin} min
                    </div>
                  </div>
                </Link>
              ))}
            </div>

            <div className="mt-3">
              <Link
                to="/rides"
                className="inline-flex items-center justify-center px-4 py-2 rounded-xl border border-amber-300 bg-white hover:bg-amber-50 text-sm font-medium"
              >
                Go to Rides →
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* Always visible: account/status (skjules i demo for å unngå backend-kall) */}
      {!demo ? (
        <section className="max-w-xl">
          <AccountStatus />
        </section>
      ) : (
        <section className="max-w-xl">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
            <div className="font-semibold mb-1">Demo (offline)</div>
            <div>
              Status/Import er skjult i demo for å unngå backend-kall. Du kan fortsatt
              klikke deg rundt i Dashboard → Rides → Ride details.
            </div>
          </div>
        </section>
      )}

      {/* Overskrift */}
      <section>
        <h1 className="text-2xl font-semibold tracking-tight mb-2">Dashboard</h1>
        <p className="text-slate-600 max-w-xl">
          Oversikt over treningen din, kalibrering og nøyaktighet i analysene.
        </p>
      </section>

      {/* Sprint 2: Strava wiring (skjules i demo for å unngå backend-kall) */}
      {!demo ? (
        <section className="max-w-xl">
          <StravaImportCard />
        </section>
      ) : (
        <section className="max-w-xl">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
            <div className="font-semibold mb-1">Demo (offline)</div>
            <div>
              Strava-import er skjult i demo for å unngå backend-kall. Bruk demo-kortet
              øverst, eller gå til Rides for å åpne en økt.
            </div>
          </div>
        </section>
      )}

      {/* To rundinger – samme ide som på CalibrationPage (dummy-verdier nå) */}
      <section className="flex flex-col md:flex-row gap-6 justify-between max-w-xl">
        <div className="flex flex-col items-center">
          <div className="h-32 w-32 rounded-full border-4 border-slate-300 flex items-center justify-center">
            <span className="text-xl font-semibold">75%</span>
          </div>
          <p className="text-sm text-slate-600 mt-2">Kalibreringsgrad</p>
        </div>

        <div className="flex flex-col items-center">
          <div className="h-32 w-32 rounded-full border-4 border-slate-300 flex items-center justify-center">
            <span className="text-xl font-semibold">90%</span>
          </div>
          <p className="text-sm text-slate-600 mt-2">Estimert watt-nøyaktighet</p>
        </div>
      </section>

      {/* Snarveier til hovedseksjoner */}
      <section className="flex flex-col gap-3 max-w-md">
        <h2 className="text-lg font-semibold">Utforsk dataene dine</h2>
        <div className="flex flex-col gap-2">
          <Link
            to="/rides"
            className="px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50"
          >
            🚴‍♂️ Rides / Økter
          </Link>
          <Link
            to="/trends"
            className="px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50"
          >
            📈 Trends / Trender
          </Link>
          <Link
            to="/goals"
            className="px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50"
          >
            🎯 Goals / Mål
          </Link>
          <Link
            to="/profile"
            className="px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50"
          >
            👤 Profile / Profil
          </Link>
        </div>
      </section>
    </div>
  );
}
