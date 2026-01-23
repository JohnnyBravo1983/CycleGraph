import { useState } from "react";
import { Link } from "react-router-dom";
import { getPostAuthRoute } from "../lib/postAuthRoute";
import { cgApi } from "../lib/cgApi";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canLogin =
    email.trim().includes("@") && password.trim().length >= 1 && !submitting;

  async function tryReadDetail(res: Response): Promise<string> {
    try {
      const data = await res.json();
      const detail =
        typeof (data as any)?.detail === "string"
          ? (data as any).detail
          : typeof (data as any)?.message === "string"
            ? (data as any).message
            : "";
      return detail || "";
    } catch {
      return "";
    }
  }

  const onLogin = async () => {
    setSubmitting(true);
    setError(null);

    try {
      const emailTrimmed = email.trim();

      // 1) POST /api/auth/login (backend setter HttpOnly cookie: cg_auth)
      const loginRes = await fetch(`${cgApi.baseUrl()}/api/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: emailTrimmed, password }),
      });

      if (!loginRes.ok) {
        const detail = await tryReadDetail(loginRes);

        if (loginRes.status === 401) {
          setError(detail || "Feil e-post eller passord.");
          return;
        }
        if (loginRes.status === 400) {
          setError(detail || "Ugyldig input. Sjekk e-post og passord.");
          return;
        }

        setError(detail || `Innlogging feilet (HTTP ${loginRes.status}).`);
        return;
      }

      // 2) Verifiser at session faktisk ble etablert: GET /api/auth/me
      const meRes = await fetch(`${cgApi.baseUrl()}/api/auth/me`, {
        method: "GET",
        credentials: "include",
      });

      if (!meRes.ok) {
        setError(
          meRes.status === 401
            ? "Login feilet – session ble ikke etablert."
            : `Kunne ikke verifisere session (HTTP ${meRes.status}).`
        );
        return;
      }

      // 3) Post-auth init + finn riktig redirect via SSOT (profile/get)
      await getPostAuthRoute(); // behold hvis den init-er stores

      // Ikke stol på AuthGate her (den kan være "guest" til neste mount).
      // Bruk profile/get som SSOT og gjør hard redirect for å re-mounte AuthGateProvider.
      let next = "/onboarding";
      try {
        const profRes = await fetch(`${cgApi.baseUrl()}/api/profile/get`, {
          method: "GET",
          credentials: "include",
        });
        if (profRes.ok) {
          const data = (await profRes.json()) as any;
          const p = data?.profile;
          const onboarded = !!p && typeof p === "object" && p.onboarded === true;
          next = onboarded ? "/dashboard" : "/onboarding";
        }
      } catch {
        // ignore -> safe default /onboarding
      }

      window.location.replace(next);
    } catch {
      setError("Network error – kunne ikke kontakte serveren.");
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
        autoComplete="email"
      />

      <input
        type="password"
        placeholder="Passord"
        className="border rounded px-3 py-2"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        autoComplete="current-password"
      />

      {error ? <div className="text-sm text-red-600">{error}</div> : null}

      <button
        type="button"
        disabled={!canLogin}
        onClick={onLogin}
        className={[
          "py-2 rounded text-white font-medium",
          canLogin
            ? "bg-slate-900 hover:bg-slate-800"
            : "bg-slate-400 cursor-not-allowed",
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
