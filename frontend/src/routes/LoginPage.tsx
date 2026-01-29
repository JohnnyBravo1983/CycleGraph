// frontend/src/routes/LoginPage.tsx
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

      await getPostAuthRoute();

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

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && canLogin) {
      onLogin();
    }
  };

  return (
    <div 
      className="min-h-screen flex items-center justify-center px-4 py-12 relative overflow-hidden"
      style={{
        backgroundImage:
          "linear-gradient(135deg, rgba(99, 102, 241, 0.92) 0%, rgba(168, 85, 247, 0.88) 100%), url('https://images.unsplash.com/photo-1541625602330-2277a4c46182?auto=format&fit=crop&w=1920&q=80')",
        backgroundSize: "cover",
        backgroundPosition: "center",
      }}
    >
      {/* Overlay */}
      <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-transparent to-black/30" />

      {/* Form Container */}
      <div className="relative z-10 w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 flex justify-center">
          <Link to="/" className="relative group">
            <div className="absolute -inset-4 rounded-2xl bg-white/10 blur-2xl transition-all duration-300 group-hover:bg-white/15" />
            <div className="relative rounded-2xl border-2 border-white/30 bg-white/10 px-6 py-4 backdrop-blur-xl shadow-[0_20px_60px_rgba(0,0,0,0.4)] ring-2 ring-white/20 transition-all duration-300 group-hover:border-white/40">
              <img
                src="/CycleGraph_Logo.png"
                alt="CycleGraph"
                className="h-16 w-auto object-contain drop-shadow-[0_8px_25px_rgba(0,0,0,0.5)]"
              />
            </div>
          </Link>
        </div>

        {/* Glass Card */}
        <div className="rounded-3xl border-2 border-white/25 bg-white/95 backdrop-blur-2xl shadow-[0_25px_80px_rgba(0,0,0,0.5)] ring-2 ring-white/30 p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-2">
              Velkommen tilbake
            </h1>
            <p className="text-sm text-slate-600 font-medium">
              Logg inn for å fortsette analysen
            </p>
          </div>

          {/* Error Alert */}
          {error && (
            <div className="mb-6 rounded-2xl border-2 border-red-300 bg-gradient-to-br from-red-50 to-red-100 px-4 py-3.5 text-sm text-red-800 font-medium shadow-lg">
              {error}
            </div>
          )}

          {/* Form */}
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-bold text-slate-800 mb-2">
                E-post
              </label>
              <input
                type="email"
                placeholder="deg@epost.no"
                className="w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-3 text-slate-900 font-medium placeholder:text-slate-400 transition-all duration-200 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 focus:outline-none"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyDown={handleKeyDown}
                autoComplete="email"
              />
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-800 mb-2">
                Passord
              </label>
              <input
                type="password"
                placeholder="••••••••"
                className="w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-3 text-slate-900 font-medium placeholder:text-slate-400 transition-all duration-200 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 focus:outline-none"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={handleKeyDown}
                autoComplete="current-password"
              />
            </div>

            {/* Login Button */}
            <button
              type="button"
              disabled={!canLogin}
              onClick={onLogin}
              className={`w-full rounded-xl px-6 py-4 text-base font-black tracking-tight transition-all duration-300 ${
                canLogin
                  ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-[0_10px_40px_rgba(99,102,241,0.4)] hover:-translate-y-1 hover:shadow-[0_15px_50px_rgba(99,102,241,0.5)] active:translate-y-0"
                  : "bg-slate-200 text-slate-400 cursor-not-allowed"
              }`}
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Logger inn...
                </span>
              ) : (
                "Logg inn"
              )}
            </button>
          </div>

          {/* Signup Link */}
          <div className="mt-6 pt-6 border-t-2 border-slate-200 text-center">
            <span className="text-sm text-slate-600 font-medium">
              Har du ikke konto?{" "}
              <Link 
                className="text-indigo-600 font-bold hover:text-indigo-700 hover:underline transition-colors" 
                to="/signup"
              >
                Registrer deg
              </Link>
            </span>
          </div>
        </div>

        {/* Back to Home Link */}
        <div className="mt-6 text-center">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm font-bold text-white/90 hover:text-white transition-colors group"
          >
            <svg className="w-4 h-4 transition-transform group-hover:-translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Tilbake til forsiden
          </Link>
        </div>
      </div>
    </div>
  );
}