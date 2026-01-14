import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getPostAuthRoute } from "../lib/postAuthRoute";

export default function LoginPage() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canLogin =
    email.trim().includes("@") &&
    password.trim().length >= 1 &&
    !submitting;

  const onLogin = async () => {
    setSubmitting(true);
    setError(null);

    try {
      // MVP: ingen ekte auth enda.
      // Etter ekte login: gjør API-kall her, og så:
      const to = await getPostAuthRoute();
      navigate("/dashboard", { replace: true });
    } catch (e) {
      setError((e as Error).message ?? "Ukjent feil ved login");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-sm mx-auto flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Logg inn</h1>

      <input
        type="email"
        placeholder="E-post"
        className="border rounded px-3 py-2"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />

      <input
        type="password"
        placeholder="Passord"
        className="border rounded px-3 py-2"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />

      {error ? <div className="text-sm text-red-600">{error}</div> : null}

      <button
        type="button"
        disabled={!canLogin}
        onClick={onLogin}
        className={[
          "py-2 rounded text-white font-medium",
          canLogin ? "bg-slate-900 hover:bg-slate-800" : "bg-slate-400 cursor-not-allowed",
        ].join(" ")}
      >
        {submitting ? "Logger inn..." : "Logg inn"}
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
