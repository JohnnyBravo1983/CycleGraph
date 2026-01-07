// frontend/src/routes/DashboardPage.tsx
import React from "react";
import { Link, useNavigate } from "react-router-dom";

import { StravaImportCard } from "../components/StravaImportCard";
import { AccountStatus } from "../components/AccountStatus";

import { isDemoMode } from "../demo/demoMode";
import { demoRides, progressionSummary } from "../demo/demoRides";

type YearKey = "2022" | "2023" | "2024" | "2025";

function toChartPoints(values: number[], w = 220, h = 46, pad = 6) {
  if (values.length === 0) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;

  return values
    .map((v, i) => {
      const x = pad + (i * (w - pad * 2)) / Math.max(values.length - 1, 1);
      const y = pad + (1 - (v - min) / span) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function DemoInsightBox() {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="text-sm font-semibold text-slate-900">What this demo shows</div>
      <div className="mt-2 text-sm text-slate-700 leading-relaxed">
        The metrics below are based on <span className="font-medium">real rides</span>{" "}
        (curated demo set, 2022–2025) analyzed through CycleGraph’s own pipeline.
      </div>

      <ul className="mt-3 space-y-1 text-sm text-slate-700">
        <li>
          • <span className="font-medium">Precision Watt (beta)</span>: a physics-based power
          model aiming for <span className="font-medium">~3–5% accuracy</span> in good
          conditions (calibrated inputs).
        </li>
        <li>
          • Compared to “estimated power” views, results can be more consistent for training
          decisions (FTP tracking, pacing, W/kg).
        </li>
        <li>
          • <span className="font-medium">Roadmap</span>: goals, progress tracking, and
          friendly competitions (leaderboards) built on the same precision metrics.
        </li>
      </ul>

      <div className="mt-3 text-xs text-slate-500">
        Note: accuracy depends on data quality (profile, terrain, weather, device streams).
        This demo is offline and reproducible.
      </div>
    </div>
  );
}

function fmtSigned(n: number, digits = 0) {
  const s = n >= 0 ? "+" : "−";
  const abs = Math.abs(n);
  return `${s}${abs.toFixed(digits)}`;
}

function fmtDeltaRow(args: {
  deltaFtpW: number;
  deltaFtpPct: number;
  deltaKg: number;
  deltaWkgPct: number;
}) {
  const { deltaFtpW, deltaFtpPct, deltaKg, deltaWkgPct } = args;

  const up = "⬆";
  const down = "⬇";

  const kgIcon = deltaKg <= 0 ? down : up;
  const ftpIcon = deltaFtpW >= 0 ? up : down;
  const wkgIcon = deltaWkgPct >= 0 ? up : down;

  return (
    <span className="text-xs text-slate-700">
      {ftpIcon} {fmtSigned(deltaFtpW, 0)}W ({fmtSigned(deltaFtpPct, 0)}%){" "}
      <span className="text-slate-300">|</span> {kgIcon} {fmtSigned(deltaKg, 1)} kg{" "}
      <span className="text-slate-300">|</span> {wkgIcon} {fmtSigned(deltaWkgPct, 0)}% W/kg
    </span>
  );
}

function yearOfRide(r: any): string {
  if (r?.year != null) return String(r.year);
  const d = String(r?.date ?? "");
  if (d.length >= 4 && /^\d{4}/.test(d)) return d.slice(0, 4);
  return "Unknown";
}

function safeNum(v: any, fallback = 0): number {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
}

const DemoProgressionPanel: React.FC = () => {
  const navigate = useNavigate();

  const years: YearKey[] = ["2022", "2023", "2024", "2025"];

  // progression series
  const ftp = years.map((y) =>
    "avgFTP" in progressionSummary[y]
      ? (progressionSummary[y] as any).avgFTP
      : (progressionSummary[y] as any).currentFTP
  ) as number[];

  const wkg = years.map((y) => safeNum((progressionSummary[y] as any).wkg));
  const weight = years.map((y) => safeNum((progressionSummary[y] as any).weight));

  const ftpPts = toChartPoints(ftp);
  const wkgPts = toChartPoints(wkg);

  const latest = progressionSummary["2025"] as any;

  // PATCH 5: Showcase filter
  const [yearFilter, setYearFilter] = React.useState<string>("All");

  const all = demoRides as any[];
  const rideYears = Array.from(new Set(all.map((r) => yearOfRide(r))))
    .filter((y) => y !== "Unknown")
    .sort();

  const filtered = yearFilter === "All" ? all : all.filter((r) => yearOfRide(r) === yearFilter);

  const newest6 = filtered
    .slice()
    .sort((a, b) => String(b.date ?? "").localeCompare(String(a.date ?? "")))
    .slice(0, 6);

  // PATCH 3: If delta fields are missing in data, compute simple deltas from series
  // (Uses series year-to-year. If you later store explicit deltas, this will still work.)
  const computedDeltas: Record<string, any> = {};
  years.forEach((y, idx) => {
    if (idx === 0) {
      computedDeltas[y] = { deltaFtpW: 0, deltaFtpPct: 0, deltaKg: 0, deltaWkgPct: 0 };
      return;
    }
    const prevY = years[idx - 1];
    const ftpPrev = safeNum(ftp[idx - 1]);
    const ftpNow = safeNum(ftp[idx]);
    const wkgPrev = safeNum(wkg[idx - 1]);
    const wkgNow = safeNum(wkg[idx]);
    const kgPrev = safeNum(weight[idx - 1]);
    const kgNow = safeNum(weight[idx]);

    const deltaFtpW = ftpNow - ftpPrev;
    const deltaFtpPct = ftpPrev !== 0 ? (deltaFtpW / ftpPrev) * 100 : 0;

    const deltaKg = kgNow - kgPrev; // negative is good (down)
    const deltaWkgPct = wkgPrev !== 0 ? ((wkgNow - wkgPrev) / wkgPrev) * 100 : 0;

    computedDeltas[y] = { deltaFtpW, deltaFtpPct, deltaKg, deltaWkgPct };
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            {/* PATCH 1: Demo banner text */}
            <div className="text-sm text-amber-900">
              🎬 <span className="font-semibold">Demo Mode</span> – Real training progression{" "}
              <span className="font-semibold">2022–2025</span> (offline &amp; deterministic)
            </div>
            <div className="text-xs text-amber-900/80 mt-1">
              Demo uses curated real rides analyzed through CycleGraph’s pipeline.
            </div>

            <div className="mt-3 text-xs font-semibold tracking-wide text-amber-700">
              DEMO MODE
            </div>
            <h2 className="text-xl font-semibold text-slate-900">
              3-års progression (FTP · vekt · W/kg)
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Basert på 12 kuraterte økter (solo) med vær og “Precision Watt” fra pipeline.
            </p>
          </div>

          <div className="flex gap-2">
            <Link
              to="/rides"
              className="inline-flex items-center rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm hover:bg-slate-50"
            >
              Se rides →
            </Link>
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-4">
          {/* PATCH 2: Insight box */}
          <DemoInsightBox />

          {/* KPI row */}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs text-slate-500">Current FTP (2025)</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">
                {latest.currentFTP ?? latest.avgFTP} W
              </div>
              <div className="mt-1 text-xs text-slate-500">Story: 210W → 260W</div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs text-slate-500">Weight (2025)</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">
                {safeNum(latest.weight).toFixed(1)} kg
              </div>
              <div className="mt-1 text-xs text-slate-500">Story: ~117kg → ~103kg</div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs text-slate-500">W/kg (2025)</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">
                {safeNum(latest.wkg).toFixed(2)}
              </div>
              <div className="mt-1 text-xs text-slate-500">Effekt + vektreduksjon</div>
            </div>
          </div>

          {/* PATCH 6: MVP hint (valgfri “wow”) */}
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="text-sm font-semibold text-slate-900">Next (MVP)</div>
            <div className="mt-1 text-sm text-slate-700">
              Set goals, track progress, and compare efforts on precision-based leaderboards.
            </div>
            <div className="mt-3 inline-flex items-center rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
              🎯 Goals &amp; Leaderboards (coming soon)
            </div>
          </div>

          {/* Trends (mini charts) */}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium text-slate-900">FTP trend</div>
                <div className="text-xs text-slate-500">{years.join(" → ")}</div>
              </div>

              <div className="mt-2 flex items-center gap-3">
                <svg width="220" height="46" viewBox="0 0 220 46" className="shrink-0">
                  <polyline
                    points={ftpPts}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="text-slate-900"
                  />
                </svg>

                <div className="text-xs text-slate-600">
                  {years.map((y, i) => (
                    <span key={y} className="mr-2">
                      <span className="font-mono">{y}</span>:{" "}
                      <span className="font-semibold text-slate-900">{ftp[i]}W</span>
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium text-slate-900">W/kg trend</div>
                <div className="text-xs text-slate-500">effekt / vekt</div>
              </div>

              <div className="mt-2 flex items-center gap-3">
                <svg width="220" height="46" viewBox="0 0 220 46" className="shrink-0">
                  <polyline
                    points={wkgPts}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="text-slate-900"
                  />
                </svg>

                <div className="text-xs text-slate-600">
                  {years.map((y, i) => (
                    <span key={y} className="mr-2">
                      <span className="font-mono">{y}</span>:{" "}
                      <span className="font-semibold text-slate-900">
                        {wkg[i].toFixed(2)}
                      </span>
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Weight row (nice table) */}
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="text-sm font-medium text-slate-900">Årsoversikt</div>

            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-slate-500">
                  <tr>
                    <th className="py-2 pr-4">Year</th>
                    <th className="py-2 pr-4">FTP</th>
                    <th className="py-2 pr-4">Weight</th>
                    <th className="py-2 pr-4">W/kg</th>

                    {/* PATCH 4: rename header */}
                    <th className="text-left text-xs font-semibold text-slate-600 py-2 pr-4">
                      Demo rides
                      <div className="text-[11px] font-normal text-slate-400">curated</div>
                    </th>

                    <th className="py-2 pr-4">Total km</th>
                    <th className="py-2 pr-4">Δ (story)</th>
                  </tr>
                </thead>

                <tbody className="text-slate-700">
                  {years.map((y, i) => {
                    const row: any = progressionSummary[y];
                    const ftpVal = row.avgFTP ?? row.currentFTP;

                    const deltaArgs = {
                      deltaFtpW: safeNum(row.deltaFtpW, computedDeltas[y].deltaFtpW),
                      deltaFtpPct: safeNum(row.deltaFtpPct, computedDeltas[y].deltaFtpPct),
                      deltaKg: safeNum(row.deltaKg, computedDeltas[y].deltaKg),
                      deltaWkgPct: safeNum(row.deltaWkgPct, computedDeltas[y].deltaWkgPct),
                    };

                    return (
                      <tr key={y} className="border-t">
                        <td className="py-2 pr-4 font-mono text-slate-900">{y}</td>
                        <td className="py-2 pr-4">{ftpVal} W</td>
                        <td className="py-2 pr-4">{Number(row.weight).toFixed(1)} kg</td>
                        <td className="py-2 pr-4">{Number(row.wkg).toFixed(2)}</td>
                        <td className="py-2 pr-4">{row.rides}</td>
                        <td className="py-2 pr-4">{Number(row.totalKm).toFixed(1)}</td>

                        {/* PATCH 3: formatted Δ */}
                        <td className="py-2 pr-4">{fmtDeltaRow(deltaArgs)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="mt-2 text-xs text-slate-500">
              Vektdata per år brukes for W/kg-demonstrasjon. For “perfect realism” kan vi senere
              hente eksakt vekt fra hver økt.
            </div>
          </div>
        </div>
      </section>

      {/* PATCH 5: Showcase rides – 6 of 12 + year filter */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <div className="text-sm font-semibold text-slate-900">Showcase rides</div>
            <div className="text-xs text-slate-500 mt-1">
              Highlights from <span className="font-medium">12 curated demo rides</span> (2022–2025)
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="text-xs text-slate-500">Year</div>
            <select
              className="text-sm rounded-xl border border-slate-200 bg-white px-2 py-1"
              value={yearFilter}
              onChange={(e) => setYearFilter(e.target.value)}
            >
              <option value="All">All</option>
              {rideYears.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>

            <span className="ml-2 inline-flex items-center rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
              Showing {Math.min(6, newest6.length)} of {filtered.length}
            </span>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-2">
          {newest6.map((r) => (
            <Link
              key={String(r.id)}
              to={`/session/${r.id}`}
              className="rounded-2xl border border-slate-200 bg-white px-4 py-3 hover:bg-slate-50 flex items-center justify-between gap-3"
            >
              <div className="min-w-0">
                <div className="font-medium text-slate-900 truncate">
                  {r.title ?? r.name ?? "Ride"}
                </div>
                <div className="text-xs text-slate-600">
                  {r.date
                    ? new Date(`${String(r.date)}T12:00:00`).toLocaleDateString("nb-NO")
                    : "—"}{" "}
                  ·{" "}
                  <span className="capitalize">
                    {String(r.rideType ?? r.tag ?? "").replace("-", " ")}
                  </span>
                </div>
              </div>

              <div className="text-right shrink-0">
                <div className="text-sm font-semibold text-slate-900">
                  {Math.round(safeNum(r.precisionWatt))} W
                </div>
                <div className="text-xs text-slate-600">
                  {(safeNum(r.distance) / 1000).toFixed(1)} km · {Math.round(safeNum(r.duration) / 60)} min
                </div>
              </div>
            </Link>
          ))}
        </div>

        <div className="mt-3">
          <Link className="text-sm text-indigo-600 hover:underline" to="/rides">
            View all demo rides →
          </Link>
        </div>
      </section>
    </div>
  );
};

export default function DashboardPage() {
  const demo = isDemoMode();

  // DEMO: use the new progression panel
  if (demo) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-6">
        <DemoProgressionPanel />
      </div>
    );
  }

  // REAL (existing) dashboard below
  return (
    <div className="flex flex-col gap-8">
      {/* Always visible: account/status */}
      <section className="max-w-xl">
        <AccountStatus />
      </section>

      {/* Overskrift */}
      <section>
        <h1 className="text-2xl font-semibold tracking-tight mb-2">Dashboard</h1>
        <p className="text-slate-600 max-w-xl">
          Oversikt over treningen din, kalibrering og nøyaktighet i analysene.
        </p>
      </section>

      {/* Sprint 2: Strava wiring */}
      <section className="max-w-xl">
        <StravaImportCard />
      </section>

      {/* Dummy rings */}
      <section className="flex flex-col md:flex-row gap-6 justify-between max-w-xl">
        <div className="flex flex-col items-center">
          <div className="h-32 w-32 rounded-full border-4 border-slate-300 flex items-center justify-center">
            <span className="text-xl font-semibold">75%</span>
          </div>
          <p className="text-sm text-slate-600 mt-2">Kalibreringsgrad</p>
        </div>

        <div className="flex flex-col items-center">
          <div className="h-32 w-32 rounded-full border-4 border-slate-300 flex items-center justify-center">
            <span className="text-xl font-semibold">90%</span>
          </div>
          <p className="text-sm text-slate-600 mt-2">Estimert watt-nøyaktighet</p>
        </div>
      </section>

      {/* Shortcuts */}
      <section className="flex flex-col gap-3 max-w-md">
        <h2 className="text-lg font-semibold">Utforsk dataene dine</h2>
        <div className="flex flex-col gap-2">
          <Link
            to="/rides"
            className="px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50"
          >
            🚴‍♂️ Rides / Økter
          </Link>
          <Link
            to="/trends"
            className="px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50"
          >
            📈 Trends / Trender
          </Link>
          <Link
            to="/goals"
            className="px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50"
          >
            🎯 Goals / Mål
          </Link>
          <Link
            to="/profile"
            className="px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-50"
          >
            👤 Profile / Profil
          </Link>
        </div>
      </section>
    </div>
  );
}
