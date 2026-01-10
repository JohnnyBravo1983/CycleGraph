// frontend/src/routes/LandingPage.tsx
import React from "react";
import { Link, useNavigate } from "react-router-dom";

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();

  function goToLiveDemo() {
    localStorage.setItem("cg_demo", "1");
    navigate("/dashboard");
  }

  const fullBleed =
    "relative left-1/2 right-1/2 -ml-[50vw] -mr-[50vw] w-screen";

  return (
    <div className={`${fullBleed} -mt-6`}>
      {/* HERO */}
      <section
        className="relative min-h-[100vh] flex items-center justify-center overflow-hidden"
        style={{
          backgroundImage:
            "linear-gradient(135deg, rgba(102,126,234,0.95) 0%, rgba(118,75,162,0.95) 100%), url('https://images.unsplash.com/photo-1541625602330-2277a4c46182?auto=format&fit=crop&w=1920&q=80')",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="absolute inset-0 bg-black/30" />

        <div className="relative z-10 mx-auto max-w-4xl px-6 text-center text-white">
          {/* LOGO */}
          <div className="mx-auto mb-5 flex items-center justify-center">
            <div className="rounded-2xl border border-white/25 bg-white/10 px-4 py-3 backdrop-blur-md shadow-[0_10px_40px_rgba(0,0,0,0.25)]">
              <img
                src="/CycleGraph_Logo.png"
                alt="CycleGraph"
                className="h-14 w-auto object-contain drop-shadow-[0_6px_18px_rgba(0,0,0,0.35)] max-md:h-12"
              />
            </div>
          </div>

          <div className="inline-flex items-center gap-2 rounded-full border border-white/30 bg-white/20 px-5 py-2 text-sm font-semibold backdrop-blur-md">
            🚀 Live Demo Preview
          </div>

          <h1 className="mt-6 text-5xl font-extrabold leading-[1.05] tracking-tight drop-shadow-[0_4px_20px_rgba(0,0,0,0.35)] max-md:text-4xl">
            Know your power.
            <br />
            Without the power meter.
          </h1>

          <p className="mt-6 mx-auto max-w-2xl text-lg leading-relaxed text-white/95 max-md:text-base">
            CycleGraph estimates your cycling power at{" "}
            <strong className="font-bold text-[#ffd700] drop-shadow-[0_2px_8px_rgba(0,0,0,0.25)]">
              ~3–5% accuracy
            </strong>{" "}
            using physics modeling — no expensive hardware required.
          </p>

          <div className="mt-10">
            <button
              type="button"
              onClick={goToLiveDemo}
              className="inline-flex items-center justify-center rounded-full bg-white px-10 py-4 text-lg font-extrabold text-[#667eea] shadow-[0_10px_40px_rgba(0,0,0,0.35)] transition-all hover:-translate-y-1 hover:bg-[#ffd700] hover:text-slate-900 hover:shadow-[0_15px_50px_rgba(0,0,0,0.45)] active:translate-y-0"
            >
              ⚡ View Live Demo
            </button>

            <p className="mt-4 text-sm text-white/85">
              Explore real training data • No signup required
            </p>
          </div>
        </div>
      </section>

      {/* LAUNCH INFO */}
      <section className="border-y-2 border-amber-500 bg-gradient-to-r from-amber-100 to-amber-200 px-6 py-7 text-center">
        <div className="mx-auto max-w-3xl">
          <p className="text-lg font-extrabold text-amber-900">
            📅 Full launch: April 1, 2026 @ cyclegraph.app
          </p>

          <p className="mt-2 text-sm text-amber-900/90">
            This is a live demo preview showcasing real training data. Stay tuned
            for goal tracking, leaderboards, and precision analysis for your own
            rides.
          </p>
        </div>
      </section>

      {/* HIGHLIGHTS */}
      <section className="bg-white px-6 py-20">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-10 md:grid-cols-3">
            <div className="rounded-2xl border-2 border-slate-200 bg-slate-50 p-8 text-center transition-all hover:-translate-y-1 hover:border-[#667eea] hover:shadow-[0_10px_30px_rgba(102,126,234,0.15)]">
              <div className="text-5xl">🎯</div>
              <h3 className="mt-4 text-xl font-bold text-slate-900">
                ~3–5% Accuracy
              </h3>
              <p className="mt-2 text-sm text-slate-600 leading-relaxed">
                Physics-based power model targeting real power meter precision
              </p>
            </div>

            <div className="rounded-2xl border-2 border-slate-200 bg-slate-50 p-8 text-center transition-all hover:-translate-y-1 hover:border-[#667eea] hover:shadow-[0_10px_30px_rgba(102,126,234,0.15)]">
              <div className="text-5xl">📊</div>
              <h3 className="mt-4 text-xl font-bold text-slate-900">
                Track Progress
              </h3>
              <p className="mt-2 text-sm text-slate-600 leading-relaxed">
                FTP, W/kg, and multi-year trends from your Strava rides
              </p>
            </div>

            <div className="rounded-2xl border-2 border-slate-200 bg-slate-50 p-8 text-center transition-all hover:-translate-y-1 hover:border-[#667eea] hover:shadow-[0_10px_30px_rgba(102,126,234,0.15)]">
              <div className="text-5xl">🏆</div>
              <h3 className="mt-4 text-xl font-bold text-slate-900">
                Compare &amp; Compete
              </h3>
              <p className="mt-2 text-sm text-slate-600 leading-relaxed">
                Leaderboards built on precision metrics (coming at launch)
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="bg-slate-900 px-6 py-12 text-center text-white">
        <div className="mx-auto max-w-4xl">
          <p className="text-sm text-white/90">
            Built by a cyclist, for cyclists. Powered by physics, proven by
            results.
          </p>

          <div className="mt-4 flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-sm">
            <Link
              to="/how-it-works"
              className="text-slate-300 hover:text-white hover:underline"
            >
              How it works
            </Link>

            <span className="text-slate-500">·</span>

            <a
              href="https://mail.google.com/mail/?view=cm&fs=1&to=johnny@cyclegraph.app&su=CycleGraph%20Live%20Demo%20Feedback"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-300 hover:text-white hover:underline"
            >
              Contact
            </a>

            <span className="text-slate-500">·</span>

            <a
              href="https://github.com/JohnnyBravo1983/CycleGraph"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-300 hover:text-white hover:underline"
            >
              GitHub
            </a>

            <span className="text-slate-500">·</span>

            <a
              href="https://www.linkedin.com/in/johnny-str%C3%B8m%C3%B8-86b21881/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-300 hover:text-white hover:underline"
            >
              LinkedIn
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
};