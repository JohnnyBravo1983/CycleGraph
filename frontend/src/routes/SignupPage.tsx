// frontend/src/routes/SignupPage.tsx
import { Link } from "react-router-dom";

export default function SignupPage() {
  return (
    <div className="max-w-sm mx-auto flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Registrer ny bruker</h1>

      <input
        type="text"
        placeholder="Fullt navn"
        className="border rounded px-3 py-2"
      />

      <input
        type="text"
        placeholder="Sykkelnavn"
        className="border rounded px-3 py-2"
      />

      <input
        type="email"
        placeholder="E-post"
        className="border rounded px-3 py-2"
      />

      <input
        type="password"
        placeholder="Passord"
        className="border rounded px-3 py-2"
      />

      <div className="text-sm text-slate-600">
        <input type="checkbox" id="consent" className="mr-2" />
        <label htmlFor="consent">
          Jeg samtykker til bruk av mine Strava-aktiviteter og mottar 3 mnd gratis CycleGraph Basic.
        </label>
      </div>

      <Link
        to="/calibration"
        className="py-2 rounded bg-slate-900 text-white text-center font-medium hover:bg-slate-800"
      >
        Gå videre til kalibrering
      </Link>

      <div className="text-sm text-slate-600">
        Har du allerede konto?{" "}
        <Link to="/login" className="underline">
          Logg inn
        </Link>
      </div>
    </div>
  );
}
