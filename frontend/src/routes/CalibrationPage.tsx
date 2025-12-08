// frontend/src/routes/CalibrationPage.tsx

import { Link } from "react-router-dom";

export default function CalibrationPage() {
  return (
    <div className="flex flex-col gap-8 max-w-lg mx-auto">

      {/* Overskrift */}
      <section>
        <h1 className="text-2xl font-semibold tracking-tight mb-2">
          Kalibrering
        </h1>
        <p className="text-slate-600">
          Fyll inn detaljene dine for å forbedre nøyaktigheten i Precision Watt-beregningene.
        </p>
      </section>

      {/* Dummy inputfelter */}
      <section className="flex flex-col gap-4">
        <input className="border rounded px-3 py-2" placeholder="Vekt (kg)" />
        <input className="border rounded px-3 py-2" placeholder="FTP" />
        <input className="border rounded px-3 py-2" placeholder="CdA" />
        <input className="border rounded px-3 py-2" placeholder="Crr" />
        <input className="border rounded px-3 py-2" placeholder="Crank Efficiency (%)" />
      </section>

      {/* To rundinger (dummy) */}
      <section className="flex flex-col md:flex-row gap-6 justify-between">
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

      {/* Proceed-knapp */}
      <Link
        to="/dashboard"
        className="py-2 rounded bg-slate-900 text-white text-center font-medium hover:bg-slate-800"
      >
        Gå videre til Dashboard
      </Link>

    </div>
  );
}
