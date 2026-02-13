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

  // ✅ Day 1: Demographics during signup (stored in auth.json)
  const [gender, setGender] = useState<"" | "male" | "female">("");
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
  const [age, setAge] = useState<string>(""); // keep as string for input control

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ageNum = Number(age);
  const ageOk = Number.isFinite(ageNum) && ageNum >= 13 && ageNum <= 100;

  const canContinue =
    !submitting &&
    fullName.trim().length >= 2 &&
    bikeName.trim().length >= 2 &&
    email.trim().includes("@") &&
    password.trim().length >= 8 &&
    gender !== "" &&
    country.trim().length >= 2 &&
    city.trim().length >= 2 &&
    ageOk &&
    consent;

  const reasons = useMemo(
    () => ({
      submitting,
      fullNameLen: fullName.trim().length,
      bikeNameLen: bikeName.trim().length,
      emailHasAt: email.trim().includes("@"),
      passwordLen: password.trim().length,
      gender,
      countryLen: country.trim().length,
      cityLen: city.trim().length,
      age,
      ageOk,
      consent,
    }),
    [
      submitting,
      fullName,
      bikeName,
      email,
      password,
      consent,
      gender,
      country,
      city,
      age,
      ageOk,
    ]
  );

  function mapSignupError(err: unknown): string {
    const anyErr = err as any;
    const status =
      typeof anyErr?.status === "number" ? (anyErr.status as number) : null;

    if (status === 409) return "That email is already in use. Try logging in.";
    if (status === 400)
      return "Invalid fields. Check your email and password (min 8 characters).";

    const msg = String(anyErr?.message ?? err ?? "");
    if (!msg) return "Unknown signup error";

    if (msg.toLowerCase().includes("failed to fetch")) {
      return "Could not reach the server. Make sure the backend is running.";
    }

    return msg;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!canContinue) {
      setError(
        "Please check the fields (password must be at least 8 characters) and consent before continuing."
      );
      return;
    }

    setSubmitting(true);
    try {
      await cgApi.authSignup(email.trim(), password, {
        gender,
        country: country.trim(),
        city: city.trim(),
        age: ageNum,
      });
      await cgApi.authMe();
      window.location.assign("/onboarding");
      return;
    } catch (err) {
      setError(mapSignupError(err));
    } finally {
      setSubmitting(false);
    }
  }

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
      {/* Overlay for better readability */}
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
          <div className="text-center mb-6">
            <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-2">
              Create your account
            </h1>
            <p className="text-sm text-slate-600 font-medium">
              Set up your profile and start analyzing your rides
            </p>
          </div>

          {/* Error Alert */}
          {error && (
            <div className="mb-6 rounded-2xl border-2 border-red-300 bg-gradient-to-br from-red-50 to-red-100 px-4 py-3.5 text-sm text-red-800 font-medium shadow-lg">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={onSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-bold text-slate-800 mb-2">
                Full name
              </label>
              <input
                className="w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-3 text-slate-900 font-medium placeholder:text-slate-400 transition-all duration-200 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 focus:outline-none"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Johnny Strømøe"
                autoComplete="name"
              />
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-800 mb-2">
                Bike name
              </label>
              <input
                className="w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-3 text-slate-900 font-medium placeholder:text-slate-400 transition-all duration-200 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 focus:outline-none"
                value={bikeName}
                onChange={(e) => setBikeName(e.target.value)}
                placeholder="Tarmac SL7"
              />
            </div>

            {/* ✅ Day 1: Demographics */}
            <div>
              <label className="block text-sm font-bold text-slate-800 mb-2">
                Gender
              </label>
              <select
                className="w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-3 text-slate-900 font-medium transition-all duration-200 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 focus:outline-none"
                value={gender}
                onChange={(e) => setGender(e.target.value as any)}
              >
                <option value="">Select…</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-800 mb-2">
                Country
              </label>
              <input
                className="w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-3 text-slate-900 font-medium placeholder:text-slate-400 transition-all duration-200 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 focus:outline-none"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                placeholder="Norway"
                autoComplete="country-name"
              />
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-800 mb-2">
                City
              </label>
              <input
                className="w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-3 text-slate-900 font-medium placeholder:text-slate-400 transition-all duration-200 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 focus:outline-none"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="Oslo"
                autoComplete="address-level2"
              />
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-800 mb-2">
                Age <span className="text-slate-500 font-medium">(13–100)</span>
              </label>
              <input
                className="w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-3 text-slate-900 font-medium placeholder:text-slate-400 transition-all duration-200 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 focus:outline-none"
                value={age}
                onChange={(e) => setAge(e.target.value)}
                type="number"
                min={13}
                max={100}
                placeholder="41"
              />
              {!submitting && age.length > 0 && !ageOk && (
                <div className="mt-2 text-xs font-semibold text-red-700">
                  Age must be between 13 and 100.
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-800 mb-2">
                Email
              </label>
              <input
                className="w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-3 text-slate-900 font-medium placeholder:text-slate-400 transition-all duration-200 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 focus:outline-none"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@email.com"
                autoComplete="email"
                type="email"
              />
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-800 mb-2">
                Password{" "}
                <span className="text-slate-500 font-medium">(min 8 characters)</span>
              </label>
              <input
                className="w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-3 text-slate-900 font-medium placeholder:text-slate-400 transition-all duration-200 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 focus:outline-none"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type="password"
                placeholder="••••••••"
                autoComplete="new-password"
              />
            </div>

            {/* Consent Checkbox */}
            <label className="flex items-start gap-3 p-4 rounded-xl bg-slate-50 border-2 border-slate-200 cursor-pointer transition-all duration-200 hover:bg-slate-100 hover:border-indigo-300">
              <input
                type="checkbox"
                className="mt-1 h-5 w-5 rounded border-2 border-slate-300 text-indigo-600 focus:ring-2 focus:ring-indigo-200 cursor-pointer"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              <span className="text-sm text-slate-700 font-medium leading-relaxed">
                I consent to CycleGraph using my Strava activities to analyze my training
              </span>
            </label>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={!canContinue}
              className={`w-full rounded-xl px-6 py-4 text-base font-black tracking-tight transition-all duration-300 ${
                canContinue
                  ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-[0_10px_40px_rgba(99,102,241,0.4)] hover:-translate-y-1 hover:shadow-[0_15px_50px_rgba(99,102,241,0.5)] active:translate-y-0"
                  : "bg-slate-200 text-slate-400 cursor-not-allowed"
              }`}
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="none"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  Creating your account...
                </span>
              ) : (
                "Create account and continue"
              )}
            </button>
          </form>

          {/* Login Link */}
          <div className="mt-6 pt-6 border-t-2 border-slate-200 text-center">
            <span className="text-sm text-slate-600 font-medium">
              Already have an account?{" "}
              <Link
                className="text-indigo-600 font-bold hover:text-indigo-700 hover:underline transition-colors"
                to="/login"
              >
                Log in
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
            <svg
              className="w-4 h-4 transition-transform group-hover:-translate-x-1"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 19l-7-7m0 0l7-7m-7 7h18"
              />
            </svg>
            Back to home
          </Link>
        </div>

        {/* Dev Helper */}
        {import.meta.env.DEV && (
          <pre className="mt-4 rounded-xl bg-black/50 backdrop-blur-xl px-4 py-3 text-xs text-white/80 font-mono overflow-auto">
            {JSON.stringify(reasons, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
