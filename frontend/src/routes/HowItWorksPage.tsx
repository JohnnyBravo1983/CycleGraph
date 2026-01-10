// frontend/src/routes/HowItWorksPage.tsx
import React from "react";
import { Link } from "react-router-dom";
import { isDemoMode } from "../demo/demoMode";

function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700">
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
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="text-base font-semibold text-slate-900">{title}</div>
      <div className="mt-3 text-sm leading-relaxed text-slate-700">{children}</div>
    </div>
  );
}

export const HowItWorksPage: React.FC = () => {
  const demo = isDemoMode();

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
    <div className="px-4 pb-16 pt-6">
      <div className="mx-auto max-w-5xl">
        {/* HERO */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700">
              What this demo shows
            </div>

            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">
              🎯 Physics-based Precision (Beta)
            </h1>

            <p className="mt-2 max-w-3xl text-sm text-slate-600">
              CycleGraph targets power estimation accuracy approaching – or exceeding – real power
              meters (typically <span className="font-semibold text-slate-900">10 000+ NOK</span>)
              without the hardware cost.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Link
              to="/dashboard"
              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Back to dashboard
            </Link>
          </div>
        </div>

        {/* TARGET + HONESTY */}
        <div className="mt-6 rounded-xl border-l-4 border-emerald-500 bg-gradient-to-br from-emerald-50/60 to-blue-50/60 p-6">
          <div className="text-base font-semibold text-slate-900">
            Target accuracy: <span className="text-emerald-700">~3–5%</span>
          </div>

          <div className="mt-1 text-sm italic text-slate-600">
            Strong hypothesis based on extensive physics modeling and sanity testing. Awaiting
            benchmark validation against real power meter data.
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {tuningParams.map((p) => (
              <Pill key={p}>{p}</Pill>
            ))}
          </div>

          <div className="mt-4 text-sm text-slate-700">
            <span className="font-semibold">Note:</span> Accuracy depends on data quality (GPS,
            elevation, weather, device streams). {demo && "This demo is offline and reproducible."}
          </div>
        </div>

        {/* DEPTH + RESULT */}
        <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card title="🔬 Unprecedented modeling depth">
            Most estimated power tools (Strava, Garmin) rely on simplified formulas with{" "}
            <strong>15–30%+ error</strong>. CycleGraph models real physics: drag, rolling resistance,
            gravity, wind, weather, aerodynamics and drivetrain losses — using deterministic,
            reproducible calculations.
          </Card>

          <Card title="Result">
            This level of modeling has never been available in a software-only solution.{" "}
            <strong>800+ hours of work</strong> have built a foundation for unprecedented precision.
            <div className="mt-4 rounded-lg border border-emerald-200 bg-white p-3 font-semibold text-emerald-700">
              Next: Benchmark validation against real power meter data (10 000+ NOK devices)
            </div>
          </Card>
        </div>

        {/* MONTHS OF WORK */}
        <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-6">
          <div className="text-base font-semibold text-slate-900">🏗️ 800+ HOURS OF WORK</div>

          <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {monthsOfWork.map((x) => (
              <div
                key={x}
                className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-700"
              >
                <span className="mr-2 font-semibold text-emerald-600">✓</span>
                {x}
              </div>
            ))}
          </div>

          <div className="mt-4 rounded-lg border border-emerald-200 bg-white p-4 text-sm font-semibold text-emerald-700">
            Model is stable, realistic and deterministic across all tested scenarios. Strong
            hypothesis: ~3–5% accuracy with good conditions.
          </div>
        </div>

        {/* Task 7 Supplement — Origin story (after 800+ HOURS OF WORK, before Integration) */}
        <section className="mt-8">
          <div className="rounded-xl border-l-4 border-blue-500 bg-sky-50 px-7 py-6 shadow-sm">
            <h3 className="flex items-center gap-2 text-[1.4rem] font-semibold text-slate-900">
              💡 Why CycleGraph exists
            </h3>

            <p className="mt-3 text-base leading-[1.7] text-slate-700">
              CycleGraph started as a personal project in 2022. I wanted two things:
            </p>

            <ol className="ml-6 mt-3 list-decimal space-y-2 pl-2 text-base leading-[1.8] text-slate-700">
              <li>A signature tech portfolio piece that demonstrated real engineering depth</li>
              <li>A precision training tool I couldn’t find anywhere else</li>
            </ol>

            <p className="mt-4 text-base leading-[1.7] text-slate-700">
              <strong className="font-semibold text-blue-600">Personal goal:</strong> Go from top
              45% (2025) to top 10% in Hervejsløpet by 2028 — using the same physics-based insights
              you see in this demo.
            </p>

            <p className="mt-4 text-base leading-[1.7] text-slate-700">
              The progression you see on the dashboard (210W → 260W, 116kg → 104kg) is real data
              from my own training. If CycleGraph works for me, it can work for you.
            </p>

            <p className="mt-5 border-t border-slate-300 pt-4 text-center text-[1.05rem] italic text-slate-500">
              Built by a cyclist, for cyclists. Powered by physics, proven by results.
            </p>
          </div>
        </section>

        {/* Task 7.4 — Integration (after Origin story, before footer nav) */}
        <section className="mt-8">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-lg font-semibold tracking-tight text-slate-900">🔗 Integration</h3>

            <p className="mt-2 text-sm text-slate-700">
              <strong>Currently:</strong> Strava (automatic analysis after upload)
            </p>
            <p className="mt-1 text-sm text-slate-700">
              <strong>Next:</strong> Direct device integrations (Garmin, Wahoo, etc.)
            </p>
          </div>
        </section>

        {/* TECH STACK */}
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card title="🦀 Rust-powered physics engine">
            Rust handles compute-heavy physics calculations with performance and memory safety.
            <div className="mt-2 font-semibold text-slate-900">
              Hundreds of hours of optimization and tuning.
            </div>

            <div className="mt-3 text-sm text-slate-600">
              Why Rust? Performance + safety for deterministic physics modeling.
            </div>
          </Card>

          <Card title="Key features (demo focus)">
            <ul className="space-y-2">
              <li>• Precision Watt (beta): physics-based power model</li>
              <li>• Compared to simplified estimated power (15–30%+ error)</li>
              <li>• Factors in drag, rolling, gravity, wind, weather, aero, drivetrain</li>
              <li>• Roadmap: goals, progress tracking, friendly competitions</li>
            </ul>
          </Card>
        </div>

        {/* FOOTER NAV */}
        <div className="mt-8 flex justify-between">
          <Link
            to="/dashboard"
            className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            ← Back
          </Link>
          <Link
            to="/leaderboards"
            className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            Go to leaderboards →
          </Link>
        </div>
      </div>
    </div>
  );
};