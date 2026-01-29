// frontend/src/routes/LandingPage.tsx
import React from "react";
import { Link, useNavigate } from "react-router-dom";

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();

  const fullBleed =
    "relative left-1/2 right-1/2 -ml-[50vw] -mr-[50vw] w-screen";

  return (
    <div className={`${fullBleed} -mt-6`}>
      {/* HERO - Lysere & Klarere */}
      <section
        className="relative min-h-[100vh] flex items-center justify-center overflow-hidden"
        style={{
          backgroundImage:
            "linear-gradient(135deg, rgba(99, 102, 241, 0.92) 0%, rgba(168, 85, 247, 0.88) 100%), url('https://images.unsplash.com/photo-1541625602330-2277a4c46182?auto=format&fit=crop&w=1920&q=80')",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        {/* Lysere overlay for bedre kontrast */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-transparent to-black/30" />

        <div className="relative z-10 mx-auto max-w-5xl px-6 text-center text-white">
          {/* LOGO - Premium glassmorphism */}
          <div className="mx-auto mb-8 flex items-center justify-center">
            <div className="relative">
              {/* Kraftigere glow */}
              <div className="absolute -inset-8 rounded-[2.5rem] bg-white/15 blur-3xl" />
              <div className="relative rounded-[2.5rem] border-2 border-white/30 bg-white/10 px-8 py-6 backdrop-blur-xl shadow-[0_20px_80px_rgba(0,0,0,0.4)] ring-2 ring-white/20">
                <img
                  src="/CycleGraph_Logo.png"
                  alt="CycleGraph"
                  className="h-24 w-auto object-contain drop-shadow-[0_12px_35px_rgba(0,0,0,0.5)] max-md:h-20"
                />
              </div>
            </div>
          </div>

          {/* HEADLINE - Råere & Tøffere */}
          <h1 className="mt-4 text-6xl font-black leading-[1.05] tracking-tight drop-shadow-[0_6px_25px_rgba(0,0,0,0.4)] max-md:text-4xl">
            Revolutionary Power Analysis.
            <br />
            <span className="bg-gradient-to-r from-white via-blue-100 to-white bg-clip-text text-transparent">
              No €800 Meter Required.
            </span>
          </h1>

          {/* SUBHEADING - Kortere & Sexier */}
          <p className="mt-8 mx-auto max-w-2xl text-xl leading-relaxed text-white/95 font-medium max-md:text-lg">
            First-ever physics modeling that turns your rides into precise watt
            data.
            <br />
            <strong className="font-extrabold text-[#fbbf24] drop-shadow-[0_3px_10px_rgba(0,0,0,0.3)]">
              ~3–5% accuracy
            </strong>{" "}
            • Zero hardware. The future is here.
          </p>

          {/* CTA - Fetere styling */}
          <div className="mt-12 flex flex-col items-center gap-4">
            <button
              type="button"
              onClick={() => navigate("/signup")}
              className="group relative inline-flex items-center justify-center overflow-hidden rounded-full bg-gradient-to-r from-white to-blue-50 px-12 py-5 text-xl font-black text-slate-900 shadow-[0_12px_45px_rgba(0,0,0,0.4)] transition-all duration-300 hover:-translate-y-2 hover:shadow-[0_18px_60px_rgba(0,0,0,0.5)] active:translate-y-0"
            >
              <span className="relative z-10">Get Started</span>
              <div className="absolute inset-0 -z-0 bg-gradient-to-r from-[#fbbf24] to-[#f59e0b] opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
            </button>

            <div className="text-base text-white/95 font-medium">
              Already have an account?{" "}
              <Link
                to="/login"
                className="font-bold underline decoration-2 underline-offset-4 hover:text-[#fbbf24] transition-colors"
              >
                Log in
              </Link>
            </div>

            {/* Badge - Tøffere styling */}
            <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-white/30 bg-white/10 px-5 py-2 backdrop-blur-md">
              <span className="text-2xl">⚡</span>
              <p className="text-sm font-bold text-white/95">
                Powered by Advanced Physics • No Hardware
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* LAUNCH INFO - Mer iøynefallende */}
      <section className="border-y-4 border-amber-400 bg-gradient-to-r from-amber-50 via-amber-100 to-amber-50 px-6 py-8 text-center shadow-[inset_0_2px_20px_rgba(0,0,0,0.1)]">
        <div className="mx-auto max-w-3xl">
          <p className="text-xl font-black text-amber-900 tracking-tight">
            🚀 Full Launch: April 1, 2026 @ cyclegraph.app
          </p>

          <p className="mt-3 text-base text-amber-900/90 font-medium">
            Goal tracking, leaderboards, and precision analysis coming soon.
            <br className="max-md:hidden" />
            Follow the journey on{" "}
            <a
              href="https://www.linkedin.com/in/johnny-str%C3%B8m%C3%B8-86b21881/"
              target="_blank"
              rel="noopener noreferrer"
              className="font-bold underline hover:text-amber-700"
            >
              LinkedIn
            </a>{" "}
            and{" "}
            <a
              href="https://github.com/JohnnyBravo1983/CycleGraph"
              target="_blank"
              rel="noopener noreferrer"
              className="font-bold underline hover:text-amber-700"
            >
              GitHub
            </a>
            .
          </p>
        </div>
      </section>

      {/* HIGHLIGHTS - Modernisert */}
      <section className="bg-gradient-to-b from-slate-50 to-white px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-8 md:grid-cols-3">
            <div className="group rounded-3xl border-2 border-slate-200 bg-white p-10 text-center transition-all duration-300 hover:-translate-y-2 hover:border-indigo-400 hover:shadow-[0_20px_60px_rgba(99,102,241,0.25)]">
              <div className="text-6xl mb-2 transition-transform duration-300 group-hover:scale-110">
                🎯
              </div>
              <h3 className="mt-5 text-2xl font-black text-slate-900">
                ~3–5% Accuracy
              </h3>
              <p className="mt-3 text-base text-slate-600 leading-relaxed font-medium">
                Physics-based power modeling that rivals real power meters
              </p>
            </div>

            <div className="group rounded-3xl border-2 border-slate-200 bg-white p-10 text-center transition-all duration-300 hover:-translate-y-2 hover:border-indigo-400 hover:shadow-[0_20px_60px_rgba(99,102,241,0.25)]">
              <div className="text-6xl mb-2 transition-transform duration-300 group-hover:scale-110">
                📊
              </div>
              <h3 className="mt-5 text-2xl font-black text-slate-900">
                Track Progress
              </h3>
              <p className="mt-3 text-base text-slate-600 leading-relaxed font-medium">
                FTP, W/kg, and multi-year trends from your Strava rides
              </p>
            </div>

            <div className="group rounded-3xl border-2 border-slate-200 bg-white p-10 text-center transition-all duration-300 hover:-translate-y-2 hover:border-indigo-400 hover:shadow-[0_20px_60px_rgba(99,102,241,0.25)]">
              <div className="text-6xl mb-2 transition-transform duration-300 group-hover:scale-110">
                🏆
              </div>
              <h3 className="mt-5 text-2xl font-black text-slate-900">
                Compare &amp; Compete
              </h3>
              <p className="mt-3 text-base text-slate-600 leading-relaxed font-medium">
                Leaderboards built on precision metrics (coming at launch)
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* FOOTER - Mer moderne */}
      <footer className="bg-slate-950 px-6 py-16 text-center text-white border-t border-slate-800">
        <div className="mx-auto max-w-4xl">
          <p className="text-base text-slate-300 font-medium">
            Built by a cyclist, for cyclists.
            <br className="md:hidden" />
            <span className="max-md:block max-md:mt-1">
              Powered by physics, proven by results.
            </span>
          </p>

          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-4 gap-y-3 text-base">
            <Link
              to="/how-it-works"
              className="text-slate-400 font-medium hover:text-white transition-colors"
            >
              How it works
            </Link>

            <span className="text-slate-700">·</span>

            <a
              href="https://mail.google.com/mail/?view=cm&fs=1&to=johnny@cyclegraph.app&su=CycleGraph%20Feedback"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 font-medium hover:text-white transition-colors"
            >
              Contact
            </a>

            <span className="text-slate-700">·</span>

            <a
              href="https://github.com/JohnnyBravo1983/CycleGraph"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 font-medium hover:text-white transition-colors"
            >
              GitHub
            </a>

            <span className="text-slate-700">·</span>

            <a
              href="https://www.linkedin.com/in/johnny-str%C3%B8m%C3%B8-86b21881/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 font-medium hover:text-white transition-colors"
            >
              LinkedIn
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
};
