// frontend/src/routes/DashboardPage.tsx
import { StravaImportCard } from "../components/StravaImportCard";
import { AccountStatus } from "../components/AccountStatus";
import { Link } from "react-router-dom";

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-8">
      {/* Always visible: account/status */}
      <section className="max-w-xl">
        <AccountStatus />
      </section>

      {/* Overskrift */}
      <section>
        <h1 className="text-2xl font-semibold tracking-tight mb-2">Dashboard</h1>
        <p className="text-slate-600 max-w-xl">
          Oversikt over treningen din, kalibrering og nøyaktighet i analysene.
        </p>
      </section>

      {/* Sprint 2: Strava wiring (status → import → list/all) */}
      <section className="max-w-xl">
        <StravaImportCard />
      </section>

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
