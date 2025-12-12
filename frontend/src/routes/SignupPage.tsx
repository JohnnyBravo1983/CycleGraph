import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getPostAuthRoute } from "../lib/postAuthRoute";

export default function SignupPage() {
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [bikeName, setBikeName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [consent, setConsent] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // MVP: ingen ekte signup enda → validerer bare skjema før vi ruter videre
  const canContinue =
    !submitting &&
    fullName.trim().length >= 2 &&
    bikeName.trim().length >= 2 &&
    email.trim().includes("@") &&
    password.trim().length >= 6 &&
    consent;

  const onContinue = async () => {
    setSubmitting(true);
    setError(null);

    try {
      // Når du senere kobler ekte signup, gjør du API-kallet her.
      // Etter "success": route basert på profil/strava-status.
      const to = await getPostAuthRoute();
      navigate(to);
    } catch (e) {
      setError((e as Error).message ?? "Ukjent feil ved registrering");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-sm mx-auto flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Registrer ny bruker</h1>

      <input
        type="text"
        placeholder="Fullt navn"
        className="border rounded px-3 py-2"
        value={fullName}
        onChange={(e) => setFullName(e.target.value)}
      />

      <input
        type="text"
        placeholder="Sykkelnavn"
        className="border rounded px-3 py-2"
        value={bikeName}
        onChange={(e) => setBikeName(e.target.value)}
      />

      <input
        type="email"
        placeholder="E-post"
        className="border rounded px-3 py-2"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />

      <input
        type="password"
        placeholder="Passord (minst 6 tegn)"
        className="border rounded px-3 py-2"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />

      <div className="text-sm text-slate-600">
        <input
          type="checkbox"
          id="consent"
          className="mr-2"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
        />
        <label htmlFor="consent">
          Jeg samtykker til bruk av mine Strava-aktiviteter og mottar 3 mnd gratis CycleGraph Basic.
        </label>
      </div>

      {error ? <div className="text-sm text-red-600">{error}</div> : null}

      <button
        type="button"
        disabled={!canContinue}
        onClick={onContinue}
        className={[
          "py-2 rounded text-white text-center font-medium",
          canContinue ? "bg-slate-900 hover:bg-slate-800" : "bg-slate-400 cursor-not-allowed",
        ].join(" ")}
      >
        {submitting ? "Fortsetter..." : "Gå videre"}
      </button>

      <div className="text-sm text-slate-600">
        Har du allerede konto?{" "}
        <Link to="/login" className="underline">
          Logg inn
        </Link>
      </div>
    </div>
  );
}
