// frontend/src/routes/LoginPage.tsx
import { Link } from "react-router-dom";

export default function LoginPage() {
  return (
    <div className="max-w-sm mx-auto flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Logg inn</h1>

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

      <button
        className="py-2 rounded bg-slate-900 text-white font-medium hover:bg-slate-800"
      >
        Logg inn
      </button>

      <div className="text-sm text-slate-600">
        Har du ikke konto?{" "}
        <Link to="/signup" className="underline">
          Registrer deg
        </Link>
      </div>
    </div>
  );
}
