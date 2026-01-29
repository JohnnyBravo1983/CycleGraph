// frontend/src/routes/HowItWorksPage.tsx
import React from "react";
import { Link } from "react-router-dom";
import { isDemoMode } from "../demo/demoMode";

function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border-2 border-indigo-200 bg-gradient-to-r from-indigo-50 to-purple-50 px-4 py-1.5 text-xs font-bold text-indigo-700 shadow-sm">
      {children}
    </span>
  );
}

function Card({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="group rounded-2xl border-2 border-slate-200 bg-white p-8 shadow-lg transition-all duration-300 hover:-translate-y-1 hover:border-indigo-300 hover:shadow-xl">
      <div className="text-xl font-black text-slate-900 mb-4">{title}</div>
      <div className="text-base leading-relaxed text-slate-700">{children}</div>
    </div>
  );
}

export const HowItWorksPage: React.FC = () => {
  const demo = isDemoMode(); // beholdes hvis brukt andre steder

  const tuningParams = [
    "Drag (CdA) – rider positions: drops, hoods, climbing",
    "Rolling resistance (Crr) – tire type, pressure, road surface",
    "Aerodynamics – wind speed, direction, rider heading (cross-wind)",
    "Weather – temperature, air pressure, air density",
    "Drivetrain – crank efficiency, transmission losses",
    "Gravity – precise elevation-based calculations",
  ];

  const monthsOfWork = [
    "Drag coefficients (CdA) tuned for rider positions",
    "Rolling resistance (Crr) across tire types and surfaces",
    "Aerodynamics: wind, direction and cross-wind effects",
    "Weather integration: temperature, pressure, air density",
    "Drivetrain losses and crank efficiency",
    "Rust optimization – hundreds of hours on physics engine",
    "Sanity testing: climbing, flat, intervals, time trials",
    "Edge case handling: GPS noise, elevation errors, weather extremes",
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50/30 px-4 pb-20 pt-8">
      <div className="mx-auto max-w-5xl">
        {/* HERO */}
        <div className="mb-8">
          <h1 className="mt-2 text-5xl font-black tracking-tight text-slate-900 max-md:text-4xl">
            🎯 Physics-based Precision
          </h1>

          <p className="mt-4 max-w-3xl text-lg leading-relaxed text-slate-700 font-medium">
            CycleGraph targets power estimation accuracy approaching – or exceeding – real power
            meters (typically <span className="font-black text-indigo-600">10 000+ NOK</span>)
            without the hardware cost.
          </p>

          <div className="mt-6">
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 rounded-xl border-2 border-slate-200 bg-white px-5 py-3 text-sm font-bold text-slate-700 shadow-md transition-all duration-200 hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-lg"
            >
              Back to dashboard
            </Link>
          </div>
        </div>

        {/* TARGET + HONESTY */}
        <div className="rounded-2xl border-l-4 border-emerald-500 bg-gradient-to-br from-emerald-50 to-blue-50 p-8 shadow-lg">
          <div className="text-2xl font-black text-slate-900">
            Target accuracy: <span className="text-emerald-600">~3–5%</span>
          </div>

          <div className="mt-3 text-base italic text-slate-700 font-medium">
            Strong hypothesis based on extensive physics modeling and testing. Awaiting
            benchmark validation against real power meter data.
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            {tuningParams.map((p) => (
              <Pill key={p}>{p}</Pill>
            ))}
          </div>

          <div className="mt-6 rounded-xl bg-white/80 backdrop-blur-sm border border-slate-200 p-4 text-sm text-slate-700 font-medium">
            <span className="font-black text-slate-900">Note:</span> Accuracy depends on data quality (GPS,
            elevation, weather, device streams).
          </div>
        </div>

   


        {/* DEPTH + RESULT */}
        <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card title="🔬 Unprecedented modeling depth">
            Most estimated power tools (Strava, Garmin) rely on simplified formulas with{" "}
            <strong className="font-black text-red-600">15–30%+ error</strong>. CycleGraph models real physics: drag, rolling resistance,
            gravity, wind, weather, aerodynamics and drivetrain losses — using deterministic,
            reproducible calculations.
          </Card>

          <Card title="Result">
            This level of modeling has never been available in a software-only solution.{" "}
            <strong className="font-black text-indigo-600">800+ hours of work</strong> have built a foundation for unprecedented precision.
            <div className="mt-5 rounded-xl border-2 border-emerald-300 bg-gradient-to-br from-emerald-50 to-white p-4 font-bold text-emerald-700 shadow-md">
              Next: Benchmark validation against real power meter data (10 000+ NOK devices)
            </div>
          </Card>
        </div>

        {/* MONTHS OF WORK */}
        <div className="mt-10 rounded-2xl border-2 border-slate-200 bg-gradient-to-br from-slate-50 to-white p-8 shadow-lg">
          <div className="text-2xl font-black text-slate-900 flex items-center gap-3">
            <span className="text-3xl">🏗️</span>
            800+ HOURS OF WORK
          </div>

          <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {monthsOfWork.map((x) => (
              <div
                key={x}
                className="rounded-xl border-2 border-slate-200 bg-white p-4 text-sm text-slate-700 font-medium shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-md"
              >
                <span className="mr-2 text-lg font-black text-emerald-600">✓</span>
                {x}
              </div>
            ))}
          </div>

          <div className="mt-6 rounded-xl border-2 border-emerald-300 bg-gradient-to-r from-emerald-50 to-white p-5 text-base font-bold text-emerald-700 shadow-md">
            Model is stable, realistic and deterministic across all tested scenarios. Strong
            hypothesis: ~3–5% accuracy with good conditions.
          </div>
        </div>

        {/* ORIGIN STORY */}
        <section className="mt-10">
          <div className="rounded-2xl border-l-4 border-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50 px-8 py-8 shadow-lg">
            <h3 className="flex items-center gap-3 text-3xl font-black text-slate-900">
              <span className="text-4xl">💡</span>
              Why CycleGraph exists
            </h3>

            <p className="mt-4 text-lg leading-relaxed text-slate-700 font-medium">
              CycleGraph started as a personal project in 2022. I wanted two things:
            </p>

            <ol className="ml-6 mt-4 list-decimal space-y-3 pl-3 text-lg leading-relaxed text-slate-700 font-medium">
              <li>A signature tech portfolio piece that demonstrated real engineering depth</li>
              <li>A precision training tool I couldn't find anywhere else</li>
            </ol>

            <div className="mt-6 rounded-xl bg-white/80 backdrop-blur-sm border-2 border-blue-200 p-5">
              <p className="text-lg leading-relaxed text-slate-700 font-medium">
                <strong className="font-black text-blue-600">Personal goal:</strong> Go from top
                45% (2025) to top 10% in Hervejsløpet by 2028 — using the same physics-based insights
                you see in this demo.
              </p>
            </div>

            <p className="mt-6 text-lg leading-relaxed text-slate-700 font-medium">
              The progression you see on the dashboard (210W → 260W, 116kg → 104kg) is real data
              from my own training. If CycleGraph works for me, it can work for you.
            </p>

            <p className="mt-6 border-t-2 border-slate-300 pt-6 text-center text-xl italic text-slate-600 font-bold">
              Built by a cyclist, for cyclists. Powered by physics, proven by results.
            </p>
          </div>
        </section>

        {/* INTEGRATION */}
        <section className="mt-10">
          <Card title="🔗 Integration">
            <p className="mt-2">
              <strong className="font-black text-slate-900">Currently:</strong>{" "}
              <span className="text-indigo-600 font-bold">Strava</span> (automatic analysis after upload)
            </p>
            <p className="mt-3">
              <strong className="font-black text-slate-900">Next:</strong>{" "}
              <span className="text-purple-600 font-bold">Direct device integrations</span> (Garmin, Wahoo, etc.)
            </p>
          </Card>
        </section>

        {/* TECH STACK */}
        <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card title="🦀 Rust-powered physics engine">
            Rust handles compute-heavy physics calculations with performance and memory safety.
            <div className="mt-4 font-black text-slate-900 text-lg">
              Hundreds of hours of optimization and tuning.
            </div>

            <div className="mt-4 rounded-xl bg-gradient-to-r from-orange-50 to-red-50 border-2 border-orange-200 p-4 text-sm text-slate-700 font-bold">
              Why Rust? Performance + safety for deterministic physics modeling.
            </div>
          </Card>

          <Card title="Key features (demo focus)">
            <ul className="space-y-3 text-base">
              <li className="flex items-start gap-2">
                <span className="text-indigo-600 font-black">•</span>
                <span><strong className="font-black">Precision Watt (beta):</strong> physics-based power model</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-indigo-600 font-black">•</span>
                <span>Compared to simplified estimated power <strong className="font-black text-red-600">(15–30%+ error)</strong></span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-indigo-600 font-black">•</span>
                <span>Factors in drag, rolling, gravity, wind, weather, aero, drivetrain</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-indigo-600 font-black">•</span>
                <span><strong className="font-black">Roadmap:</strong> goals, progress tracking, friendly competitions</span>
              </li>
            </ul>
          </Card>
        </div>

        {/* FOOTER NAV */}
        <div className="mt-12 flex flex-col sm:flex-row gap-4 justify-between">
          <Link
            to="/dashboard"
            className="inline-flex items-center justify-center gap-2 rounded-xl border-2 border-slate-200 bg-white px-6 py-4 text-base font-bold text-slate-700 shadow-lg transition-all duration-300 hover:-translate-y-1 hover:border-indigo-300 hover:shadow-xl"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back
          </Link>
          <Link
            to="/leaderboards"
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-6 py-4 text-base font-bold text-white shadow-lg transition-all duration-300 hover:-translate-y-1 hover:shadow-xl"
          >
            Go to leaderboards
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </Link>
        </div>
      </div>
    </div>
  );
};