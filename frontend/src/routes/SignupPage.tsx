// frontend/src/routes/SignupPage.tsx
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { cgApi } from "../lib/cgApi";

export default function SignupPage() {
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [bikeName, setBikeName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [consent, setConsent] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canContinue =
    !submitting &&
    fullName.trim().length >= 2 &&
    bikeName.trim().length >= 2 &&
    email.trim().includes("@") &&
    password.trim().length >= 8 &&
    consent;

  const reasons = useMemo(
    () => ({
      submitting,
      fullNameLen: fullName.trim().length,
      bikeNameLen: bikeName.trim().length,
      emailHasAt: email.trim().includes("@"),
      passwordLen: password.trim().length,
      consent,
    }),
    [submitting, fullName, bikeName, email, password, consent]
  );

  function mapSignupError(err: unknown): string {
    const anyErr = err as any;

    // ApiError from cgApi (has .status)
    const status = typeof anyErr?.status === "number" ? (anyErr.status as number) : null;

    if (status === 409) return "E-post er allerede i bruk. Prøv å logge inn.";
    if (status === 400) return "Ugyldige felt. Sjekk e-post og passord (minst 8 tegn).";

    const msg = String(anyErr?.message ?? err ?? "");
    if (!msg) return "Ukjent feil ved registrering";

    // Slightly nicer network message
    if (msg.toLowerCase().includes("failed to fetch")) {
      return "Kunne ikke kontakte server. Sjekk at backend kjører.";
    }

    return msg;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!canContinue) {
      setError("Sjekk feltene (minst 8 tegn passord) og samtykke før du fortsetter.");
      return;
    }

    setSubmitting(true);
    try {
      // 1) Create account in backend
      await cgApi.authSignup(email.trim(), password);

      // 2) Verify session is established (DoD: /api/auth/me -> 200)
      await cgApi.authMe();

      // 3) Redirect explicitly to onboarding (Task 1.6 scope)
      window.location.assign("/onboarding");
      return;
    } catch (err) {
      setError(mapSignupError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-md mx-auto">
      <h1 className="text-2xl font-semibold tracking-tight mb-2">Opprett konto</h1>
      <p className="text-sm text-slate-600 mb-6">
        Lag en konto for å lagre profil og analysere økter.
      </p>

      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Fullt navn</label>
          <input
            className="w-full rounded-xl border px-3 py-2"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Johnny Strømøe"
            autoComplete="name"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Sykkelnavn</label>
          <input
            className="w-full rounded-xl border px-3 py-2"
            value={bikeName}
            onChange={(e) => setBikeName(e.target.value)}
            placeholder="Tarmac SL7"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">E-post</label>
          <input
            className="w-full rounded-xl border px-3 py-2"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="deg@epost.no"
            autoComplete="email"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Passord (minst 8 tegn)
          </label>
          <input
            className="w-full rounded-xl border px-3 py-2"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            autoComplete="new-password"
          />
        </div>

        <label className="flex items-start gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            className="mt-1"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
          />
          <span>
            Jeg samtykker til at CycleGraph kan bruke mine Strava-aktiviteter for å analysere trening.
          </span>
        </label>

        <button
          type="submit"
          disabled={!canContinue}
          className={`w-full rounded-xl px-4 py-2 text-sm font-semibold ${
            canContinue
              ? "bg-slate-900 text-white hover:bg-slate-800"
              : "bg-slate-200 text-slate-500 cursor-not-allowed"
          }`}
        >
          {submitting ? "Oppretter..." : "Bekreft og gå videre"}
        </button>

        <div className="text-sm text-slate-600 flex items-center justify-between">
          <span>Har du konto allerede?</span>
          <Link className="text-slate-900 font-medium" to="/login">
            Logg inn
          </Link>
        </div>

        {/* Dev helper */}
        {import.meta.env.DEV && (
          <pre className="mt-4 text-xs text-slate-500 whitespace-pre-wrap">
            {JSON.stringify(reasons, null, 2)}
          </pre>
        )}
      </form>
    </div>
  );
}
