// frontend/src/routes/DashboardPage.tsx
import React from "react";
import { Link } from "react-router-dom";
import { cgApi } from "../lib/cgApi";
import { StravaImportCard } from "../components/StravaImportCard";
import { isDemoMode } from "../demo/demoMode";
import { demoRides, progressionSummary } from "../demo/demoRides";

// ✅ Patch 4a.2
import { leaderboardMockData } from "../demo/leaderboardMockData";

type YearKey = "2022" | "2023" | "2024" | "2025";

// ----------------------------
// Trend helpers (for tooltips)
// ----------------------------
type TrendPoint = {
  year: string;
  value: number;
  valueLabel: string; // "235 W" / "2.12 W/kg"
  deltaLabel?: string; // "+25 W (+12%) ↑"
  deltaSign?: "pos" | "neg" | "zero";
};

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function fmtSigned(n: number, digits = 0) {
  const s = n >= 0 ? "+" : "−";
  return `${s}${Math.abs(n).toFixed(digits)}`;
}

function pctChange(curr: number, prev: number) {
  if (!prev) return 0;
  return (curr - prev) / prev;
}

// PATCH 3: exact Tailwind tones
function deltaStyle(sign?: TrendPoint["deltaSign"]) {
  if (sign === "pos") return "text-emerald-500"; // ~#10b981
  if (sign === "neg") return "text-red-500"; // ~#ef4444
  return "text-slate-500";
}

function buildSparkPoints(values: number[], w = 220, h = 46, pad = 6) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;

  return values.map((v, i) => {
    const x = pad + (i * (w - pad * 2)) / Math.max(values.length - 1, 1);
    const y = pad + (1 - (v - min) / span) * (h - pad * 2);
    return { x, y, v };
  });
}

function pointsToPath(pts: { x: number; y: number }[]) {
  if (!pts.length) return "";
  return pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
}

function MiniTrendChart({
  title,
  points,
  width = 240,
  height = 56,
}: {
  title: string;
  points: TrendPoint[];
  width?: number;
  height?: number;
}) {
  const pad = 8;
  const w = width;
  const h = height;

  const values = points.map((p) => p.value);
  const pts = buildSparkPoints(values, w, h, pad);
  const pathD = pointsToPath(pts);

  const wrapRef = React.useRef<HTMLDivElement | null>(null);
  const [activeIdx, setActiveIdx] = React.useState<number | null>(null);
  const [locked, setLocked] = React.useState(false);
  const [pos, setPos] = React.useState<{ x: number; y: number }>({ x: 0, y: 0 });

  function hide() {
    setActiveIdx(null);
    setLocked(false);
  }

  function setTooltipFromEvent(e: React.MouseEvent | React.TouchEvent, idx: number) {
    const el = wrapRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();

    const clientX =
      "touches" in e ? (e.touches[0]?.clientX ?? rect.left) : (e as React.MouseEvent).clientX;
    const clientY =
      "touches" in e ? (e.touches[0]?.clientY ?? rect.top) : (e as React.MouseEvent).clientY;

    const x = clamp(clientX - rect.left, 0, rect.width);
    const y = clamp(clientY - rect.top, 0, rect.height);

    setPos({ x, y });
    setActiveIdx(idx);
  }

  React.useEffect(() => {
    function onDocDown(ev: MouseEvent | TouchEvent) {
      const el = wrapRef.current;
      if (!el) return;
      if (!el.contains(ev.target as Node)) hide();
    }
    document.addEventListener("mousedown", onDocDown);
    document.addEventListener("touchstart", onDocDown, { passive: true });
    return () => {
      document.removeEventListener("mousedown", onDocDown);
      document.removeEventListener("touchstart", onDocDown);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const active = activeIdx != null ? points[activeIdx] : null;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-slate-900">{title}</div>
        <div className="text-xs text-slate-500">Hover / tap points</div>
      </div>

      <div ref={wrapRef} className="relative mt-3">
        <svg
          width={w}
          height={h}
          className="block w-full"
          viewBox={`0 0 ${w} ${h}`}
          onMouseLeave={() => {
            if (!locked) setActiveIdx(null);
          }}
        >
          <path
            d={pathD}
            fill="none"
            stroke="currentColor"
            className="text-slate-700"
            strokeWidth="2"
          />

          {pts.map((p, idx) => (
            <g key={idx}>
              <circle
                cx={p.x}
                cy={p.y}
                r={10}
                fill="transparent"
                onMouseEnter={(e) => {
                  setLocked(false);
                  setTooltipFromEvent(e, idx);
                }}
                onMouseMove={(e) => {
                  if (!locked) setTooltipFromEvent(e, idx);
                }}
                onClick={(e) => {
                  setLocked(true);
                  setTooltipFromEvent(e, idx);
                }}
                onTouchStart={(e) => {
                  setLocked(true);
                  setTooltipFromEvent(e, idx);
                }}
              />
              <circle
                cx={p.x}
                cy={p.y}
                r={3.2}
                className={idx === activeIdx ? "fill-slate-900" : "fill-slate-500"}
              />
            </g>
          ))}
        </svg>

        {active && (
          <div
            className="absolute z-10 pointer-events-none"
            style={{
              left: clamp(pos.x + 10, 0, w - 180),
              top: clamp(pos.y + 10, 0, h - 10),
              maxWidth: 180,
            }}
          >
            {/* caret */}
            <div className="absolute -top-2 left-3 h-3 w-3 rotate-45 border-l border-t border-slate-200 bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)]" />

            <div
              className={[
                "rounded-lg border border-slate-200 bg-white",
                "shadow-[0_4px_12px_rgba(0,0,0,0.15)]",
                "px-4 py-3",
                "transition-opacity duration-200 ease-in-out",
                "text-slate-800",
              ].join(" ")}
            >
              <div className="text-[13px] font-semibold text-slate-500">{active.year}</div>

              <div className="text-[16px] font-medium text-slate-800 leading-tight mt-0.5">
                {active.valueLabel}
              </div>

              {active.deltaLabel ? (
                <div className={`text-[14px] font-normal mt-0.5 ${deltaStyle(active.deltaSign)}`}>
                  {active.deltaLabel}
                </div>
              ) : (
                <div className="text-[14px] font-normal mt-0.5 text-slate-500">Baseline</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ----------------------------
// Existing helpers (demo view)
// ----------------------------
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
        (curated demo set, 2022–2025) analyzed through CycleGraph's own pipeline.
      </div>

      <ul className="mt-3 space-y-1 text-sm text-slate-700">
        <li>
          • <span className="font-medium">Precision Watt (beta)</span>: a physics-based power model
          aiming for <span className="font-medium">~3–5% accuracy</span> in good conditions
          (calibrated inputs).
        </li>
        <li>
          • Compared to "estimated power" views, results can be more consistent for training
          decisions (FTP tracking, pacing, W/kg).
        </li>
        <li>
          • <span className="font-medium">Roadmap</span>: goals, progress tracking, and friendly
          competitions (leaderboards) built on the same precision metrics.
        </li>
      </ul>

      <div className="mt-3 text-xs text-slate-500">
        Note: accuracy depends on data quality (profile, terrain, weather, device streams). This
        demo is offline and reproducible.
      </div>
    </div>
  );
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

// Build TrendPoints from series
function buildTrendPoints(
  years: string[],
  vals: number[],
  fmt: (v: number) => string,
  unit: string,
  deltaDigits: number
): TrendPoint[] {
  return years.map((y, i) => {
    const v = vals[i];
    if (i === 0) return { year: y, value: v, valueLabel: fmt(v) };

    const prev = vals[i - 1];
    const d = v - prev;
    const pct = Math.round(pctChange(v, prev) * 100);
    const sign: TrendPoint["deltaSign"] = d > 0 ? "pos" : d < 0 ? "neg" : "zero";
    const arrow = d > 0 ? "↑" : d < 0 ? "↓" : "→";

    return {
      year: y,
      value: v,
      valueLabel: fmt(v),
      deltaSign: sign,
      deltaLabel: `${fmtSigned(d, deltaDigits)} ${unit} (${fmtSigned(pct, 0)}%) ${arrow}`,
    };
  });
}

// ----------------------------
// Patch 4a.P1 – Leaderboard helpers
// ----------------------------
type LbEntry = {
  name: string;
  ftp: number;
  weight: number;
  wkg: number;
  isCurrentUser?: boolean;
};

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const a = parts[0]?.[0] ?? "?";
  const b = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (a + b).toUpperCase();
}

function sortByMetric(rows: LbEntry[], metric: "ftp" | "wkg") {
  return [...rows].sort((a, b) => (metric === "ftp" ? b.ftp - a.ftp : b.wkg - a.wkg));
}

// Top N, but always include current user (with "…" separator) if outside top N
function topWithCurrent(rows: LbEntry[], metric: "ftp" | "wkg", n = 5) {
  const sorted = sortByMetric(rows, metric).map((r, idx) => ({ ...r, _rank: idx + 1 }));
  const top = sorted.slice(0, n);
  const me = sorted.find((r) => r.isCurrentUser);

  const inTop = me ? top.some((r) => r.name === me.name) : false;
  if (!me || inTop) return { rows: top, showEllipsis: false };

  return { rows: [...top, me], showEllipsis: true };
}

const DemoProgressionPanel: React.FC = () => {
  const years: YearKey[] = ["2022", "2023", "2024", "2025"];

  const ftp = years.map((y) =>
    "avgFTP" in (progressionSummary[y] as any)
      ? (progressionSummary[y] as any).avgFTP
      : (progressionSummary[y] as any).currentFTP
  ) as number[];

  const wkg = years.map((y) => safeNum((progressionSummary[y] as any).wkg));
  const weight = years.map((y) => safeNum((progressionSummary[y] as any).weight));

  const latest = progressionSummary["2025"] as any;

  // Showcase filter
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

  // Compute deltas (fallback if not present in progressionSummary)
  const computedDeltas: Record<string, any> = {};
  years.forEach((y, idx) => {
    if (idx === 0) {
      computedDeltas[y] = { deltaFtpW: 0, deltaFtpPct: 0, deltaKg: 0, deltaWkgPct: 0 };
      return;
    }
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

  // Trend points for MiniTrendChart
  const yearStrings = years.map((y) => String(y));
  const ftpTrendPoints = buildTrendPoints(
    yearStrings,
    ftp.map((v) => safeNum(v)),
    (v) => `${Math.round(v)} W`,
    "W",
    0
  );
  const wkgTrendPoints = buildTrendPoints(
    yearStrings,
    wkg.map((v) => safeNum(v)),
    (v) => `${v.toFixed(2)} W/kg`,
    "W/kg",
    2
  );

  return (
    <div className="space-y-6">
      {/* HEADER BRAND (logo + back) */}
      <section className="flex items-center justify-between">
        <Link
          to="/"
          className="inline-flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-2 shadow-sm hover:bg-slate-50"
          title="Back to landing"
        >
          <img
            src="/CycleGraph_Logo.png"
            alt="CycleGraph"
            className="h-8 w-auto object-contain"
          />
          <span className="text-sm font-semibold text-slate-900">CycleGraph</span>
        </Link>

        <div className="text-xs text-slate-500">Demo dashboard</div>
      </section>

      {/* HERO V2 — WOW (replaces old hero box) */}
      <section className="mb-12">
        <div
          className="relative flex items-center gap-7 overflow-hidden rounded-2xl p-10 shadow-[0_12px_40px_rgba(102,126,234,0.40)] transition-transform duration-300 hover:-translate-y-1 hover:shadow-[0_16px_50px_rgba(102,126,234,0.50)] max-md:flex-col max-md:text-center max-md:p-8"
          style={{
            background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            color: "white",
          }}
        >
          {/* Subtle overlay */}
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(circle at top right, rgba(255,255,255,0.10) 0%, transparent 60%)",
            }}
          />

          {/* Icon */}
          <div className="relative z-10 flex-none text-6xl leading-none drop-shadow-[0_4px_12px_rgba(0,0,0,0.30)] max-md:text-5xl">
            ⚡
          </div>

          {/* Content */}
          <div className="relative z-10 min-w-0 flex-1">
            <h2 className="text-4xl font-extrabold tracking-tight leading-tight max-md:text-3xl">
              Power estimation without the hardware cost
            </h2>

            <p className="mt-3 text-lg leading-relaxed text-white/95 max-md:text-base">
              Targeting{" "}
              <strong className="text-[1.2em] font-bold text-[#ffd700] drop-shadow-[0_2px_8px_rgba(0,0,0,0.20)]">
                ~3–5% accuracy
              </strong>{" "}
              No power meter required.
            </p>

            <Link
              to="/how-it-works"
              className="mt-6 inline-flex items-center justify-center rounded-xl bg-white px-8 py-3 text-base font-semibold text-[#667eea] shadow-[0_4px_12px_rgba(0,0,0,0.15)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_6px_20px_rgba(0,0,0,0.25)] active:translate-y-0"
            >
              See how it works →
            </Link>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="text-sm text-amber-900">
              🎬 <span className="font-semibold">Demo Mode</span> – Real training progression{" "}
              <span className="font-semibold">2022–2025</span> (offline &amp; deterministic)
            </div>
            <div className="text-xs text-amber-900/80 mt-1">
              Demo uses curated real rides analyzed through CycleGraph's pipeline.
            </div>

            <div className="mt-3 text-xs font-semibold tracking-wide text-amber-700">DEMO MODE</div>
            <h2 className="text-xl font-semibold text-slate-900">
              Multi-year progression (FTP · weight · W/kg)
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Based on 12 curated rides (solo), with weather and "Precision Watt" from the pipeline.
            </p>
          </div>

          <div className="flex gap-2">
            <Link
              to="/rides"
              className="inline-flex items-center rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm hover:bg-slate-50"
            >
              View rides →
            </Link>
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-4">
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
              <div className="mt-1 text-xs text-slate-500">Power + weight loss</div>
            </div>
          </div>

          {/* Trends (tooltips) */}
          <div className="grid gap-4 md:grid-cols-2">
            <MiniTrendChart title="FTP trend" points={ftpTrendPoints} />
            <MiniTrendChart title="W/kg trend" points={wkgTrendPoints} />
          </div>

          {/* Task 7.3 — Next (MVP) hint (under trends, before Showcase rides) */}
          <section className="mt-4">
            <div className="rounded-2xl border border-slate-200 bg-sky-50 p-5">
              <h4 className="text-base font-semibold text-slate-900">Next (MVP)</h4>
              <p className="mt-1 text-sm text-slate-700">
                Set goals, track progress, and compare performance on precision-based leaderboards.
              </p>
            </div>
          </section>

          {/* Year overview */}
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="text-sm font-medium text-slate-900">Year overview</div>

            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-slate-500">
                  <tr>
                    <th className="py-2 pr-4">Year</th>
                    <th className="py-2 pr-4">FTP</th>
                    <th className="py-2 pr-4">Weight</th>
                    <th className="py-2 pr-4">W/kg</th>
                    <th className="text-left text-xs font-semibold text-slate-600 py-2 pr-4">
                      Demo rides
                      <div className="text-[11px] font-normal text-slate-400">curated</div>
                    </th>
                    <th className="py-2 pr-4">Total km</th>
                    <th className="py-2 pr-4">Δ (story)</th>
                  </tr>
                </thead>

                <tbody className="text-slate-700">
                  {years.map((y) => {
                    const row: any = progressionSummary[y];
                    const ftpVal = row.avgFTP ?? row.currentFTP;

                    const deltaArgs = {
                      deltaFtpW: safeNum(row.deltaFtpW, computedDeltas[y].deltaFtpW),
                      deltaFtpPct: safeNum(row.deltaFtpPct, computedDeltas[y].deltaFtpPct),
                      deltaKg: safeNum(row.deltaKg, computedDeltas[y].deltaKg),
                      deltaWkgPct: safeNum(row.deltaWkgPct, computedDeltas[y].deltaWkgPct),
                    };

                    const is2025 = String(y) === "2025";
                    const tdBase = "py-2 pr-4";
                    const tdFirst = is2025
                      ? "pl-5 py-2 pr-4 font-mono text-slate-900"
                      : "py-2 pr-4 font-mono text-slate-900";

                    const ftpPctBadge = row.deltaFtpPct ?? computedDeltas[y].deltaFtpPct;
                    const kgDeltaBadge = row.deltaKg ?? computedDeltas[y].deltaKg;
                    const wkgPctBadge = row.deltaWkgPct ?? computedDeltas[y].deltaWkgPct;

                    return (
                      <tr
                        key={y}
                        className={
                          is2025
                            ? "bg-gradient-to-r from-emerald-50 to-emerald-100 font-semibold border-l-4 border-emerald-500"
                            : "border-t"
                        }
                      >
                        <td className={tdFirst}>{y}</td>

                        <td className={tdBase}>
                          {ftpVal} W{" "}
                          {is2025 && (
                            <span className="ml-2 inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                              {`+${Math.round(safeNum(ftpPctBadge))}%`}
                            </span>
                          )}
                        </td>

                        <td className={tdBase}>
                          {Number(row.weight).toFixed(1)} kg{" "}
                          {is2025 && (
                            <span className="ml-2 inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                              {`${fmtSigned(safeNum(kgDeltaBadge), 1)} kg`}
                            </span>
                          )}
                        </td>

                        <td className={tdBase}>
                          {Number(row.wkg).toFixed(2)}{" "}
                          {is2025 && (
                            <span className="ml-2 inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                              {`+${Math.round(safeNum(wkgPctBadge))}%`}
                            </span>
                          )}
                        </td>

                        <td className={tdBase}>{row.rides}</td>
                        <td className={tdBase}>{Number(row.totalKm).toFixed(1)}</td>
                        <td className={tdBase}>{fmtDeltaRow(deltaArgs)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="mt-2 text-xs text-slate-500">
              Weight is captured per ride and factored directly into the W/kg calculations.
            </div>
          </div>

          {/* Task 7.2 — Profile Precision (after Year overview, before Showcase rides) */}
          <section className="mt-8 mb-8">
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="text-lg font-semibold tracking-tight text-slate-900">
                🎯 Profile precision
              </h3>

              <p className="mt-2 text-sm text-slate-600">
                CycleGraph personalizes estimated power based on:
              </p>

              <ul className="mt-4 space-y-2 text-sm text-slate-700">
                <li>
                  <span className="mr-2 font-semibold text-emerald-600">✓</span>
                  Rider: 104.4 kg (down from 116.8 kg in 2022)
                </li>
                <li>
                  <span className="mr-2 font-semibold text-emerald-600">✓</span>Bike: 8 kg road bike,
                  28mm tires
                </li>
                <li>
                  <span className="mr-2 font-semibold text-emerald-600">✓</span>Drivetrain: 96% crank
                  efficiency
                </li>
                <li>
                  <span className="mr-2 font-semibold text-emerald-600">✓</span>Position: Road (CdA
                  0.300, Crr 0.0040)
                </li>
              </ul>

              <p className="mt-4 text-sm italic text-slate-500">
                → A better profile = more precise estimates
              </p>

              {/* PATCH FP-5 — replace confusing disabled button with info note */}
              <div className="mt-4 rounded-xl border-l-4 border-blue-600 bg-sky-50 p-4 text-sm text-blue-900">
                💡 Full profile customization available at launch — adjust your bike, position, and
                weight for optimal precision.
              </div>
            </div>
          </section>
        </div>
      </section>

      {/* Showcase rides */}
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
                    ? new Date(`${String(r.date)}T12:00:00`).toLocaleDateString("en-US")
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
                  {(safeNum(r.distance) / 1000).toFixed(1)} km ·{" "}
                  {Math.round(safeNum(r.duration) / 60)} min
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

      {/* ✅ Patch 4a.P2: Premium Leaderboards teaser widget */}
      <section className="rounded-xl border border-slate-200 bg-white p-5 mt-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-slate-800">🏆 Leaderboards</h2>
          <Link to="/leaderboards" className="text-sm font-medium text-emerald-600 hover:underline">
            View all →
          </Link>
        </div>

        {/* FTP */}
        {(() => {
          const { rows } = topWithCurrent(leaderboardMockData as any, "ftp", 5);
          return (
            <div className="mb-6">
              <div className="text-xs font-semibold text-slate-500 uppercase mb-2">
                FTP Leaderboard
              </div>

              <div className="overflow-hidden rounded-lg border border-slate-200">
                {rows.map((u: any, idx: number) => {
                  const rank = u._rank ?? idx + 1;
                  const top3 = rank <= 3;
                  const isMe = !!u.isCurrentUser;

                  return (
                    <div
                      key={`ftp-${u.name}`}
                      className={[
                        "grid grid-cols-[40px_48px_1fr_auto] gap-3 items-center",
                        "px-4 py-3 border-b border-slate-200 last:border-b-0",
                        idx % 2 === 0 ? "bg-white" : "bg-slate-50",
                        "transition-colors duration-150 hover:bg-slate-100",
                        isMe
                          ? "bg-gradient-to-r from-emerald-50/60 to-white border-l-[3px] border-l-emerald-500 font-semibold"
                          : "",
                      ].join(" ")}
                    >
                      <div
                        className={[
                          "text-center text-[16px] font-bold",
                          top3 ? "text-emerald-600" : "text-slate-500",
                        ].join(" ")}
                      >
                        {rank}
                      </div>

                      <div
                        className={[
                          "h-10 w-10 rounded-full flex items-center justify-center",
                          isMe
                            ? "bg-emerald-100 text-emerald-600 text-[18px]"
                            : "bg-slate-200 text-slate-600 text-[14px]",
                          "font-semibold",
                        ].join(" ")}
                        title={isMe ? "You (demo user)" : u.name}
                      >
                        {isMe ? "⚡" : initials(u.name)}
                      </div>

                      <div className="text-slate-800 truncate">{u.name}</div>

                      <div
                        className={[
                          "text-slate-800 font-semibold",
                          isMe ? "text-emerald-600" : "",
                        ].join(" ")}
                      >
                        {u.ftp} W{isMe ? " ⚡" : ""}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })()}

        {/* W/kg */}
        {(() => {
          const { rows, showEllipsis } = topWithCurrent(leaderboardMockData as any, "wkg", 5);
          return (
            <div>
              <div className="text-xs font-semibold text-slate-500 uppercase mb-2">
                W/kg Leaderboard
              </div>

              <div className="overflow-hidden rounded-lg border border-slate-200">
                {rows.map((u: any, idx: number) => {
                  const rank = u._rank ?? idx + 1;
                  const top3 = rank <= 3;
                  const isMe = !!u.isCurrentUser;

                  const isLast = idx === rows.length - 1;
                  const showDotsHere = showEllipsis && isLast;

                  return (
                    <React.Fragment key={`wkg-${u.name}`}>
                      {showDotsHere && (
                        <div className="px-4 py-2 text-xs text-slate-400 bg-white border-b border-slate-200">
                          …
                        </div>
                      )}

                      <div
                        className={[
                          "grid grid-cols-[40px_48px_1fr_auto] gap-3 items-center",
                          "px-4 py-3 border-b border-slate-200 last:border-b-0",
                          idx % 2 === 0 ? "bg-white" : "bg-slate-50",
                          "transition-colors duration-150 hover:bg-slate-100",
                          isMe
                            ? "bg-gradient-to-r from-emerald-50/60 to-white border-l-[3px] border-l-emerald-500 font-semibold"
                            : "",
                        ].join(" ")}
                      >
                        <div
                          className={[
                            "text-center text-[16px] font-bold",
                            top3 ? "text-emerald-600" : "text-slate-500",
                          ].join(" ")}
                        >
                          {rank}
                        </div>

                        <div
                          className={[
                            "h-10 w-10 rounded-full flex items-center justify-center",
                            isMe
                              ? "bg-emerald-100 text-emerald-600 text-[18px]"
                              : "bg-slate-200 text-slate-600 text-[14px]",
                            "font-semibold",
                          ].join(" ")}
                          title={isMe ? "You (demo user)" : u.name}
                        >
                          {isMe ? "⚡" : initials(u.name)}
                        </div>

                        <div className="text-slate-800 truncate">{u.name}</div>

                        <div
                          className={[
                            "text-slate-800 font-semibold",
                            isMe ? "text-emerald-600" : "",
                          ].join(" ")}
                        >
                          {Number(u.wkg).toFixed(2)} W/kg{isMe ? " ⚡" : ""}
                        </div>
                      </div>
                    </React.Fragment>
                  );
                })}
              </div>
            </div>
          );
        })()}
      </section>
    </div>
  );
};

// ========================================
// 🚀 REAL MODE DASHBOARD V3 - CLEAN & FOCUSED
// ========================================

export default function DashboardPage() {
  const demo = isDemoMode();

  async function onLogout() {
    try {
      await fetch(`${cgApi.baseUrl()}/api/auth/logout`, { method: "POST", credentials: "include" });
    } finally {
      window.location.replace("/login");
    }
  }

  if (demo) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-6">
        <DemoProgressionPanel />
      </div>
    );
  }

  // ========================================
  // 🎨 REAL MODE V3 - STREAMLINED
  // ========================================
  return (
    <div 
      className="min-h-screen"
      style={{
        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
      }}
    >
      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* HEADER */}
        <header className="flex items-center justify-between mb-8">
          <Link
            to="/"
            className="inline-flex items-center gap-3 rounded-2xl border border-white/20 bg-white/10 backdrop-blur-sm px-4 py-2.5 shadow-lg hover:bg-white/20 transition-all"
          >
            <img src="/CycleGraph_Logo.png" alt="CycleGraph" className="h-8 w-auto" />
            <span className="text-sm font-semibold text-white">CycleGraph</span>
          </Link>

          <button
            type="button"
            onClick={onLogout}
            className="px-4 py-2.5 rounded-2xl border border-white/20 bg-white/10 backdrop-blur-sm text-sm font-medium text-white shadow-lg hover:bg-white/20 transition-all"
          >
            Logg ut
          </button>
        </header>

        {/* 🔥 HERO: TRENDS (WOW FACTOR) */}
        <section className="mb-6">
          <div className="rounded-3xl bg-white/95 backdrop-blur-sm p-8 shadow-[0_20px_60px_rgba(0,0,0,0.3)]">
            
            <div className="flex items-start gap-4 mb-6">
              <div className="flex-none">
                <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center text-white text-2xl font-bold shadow-lg">
                  📈
                </div>
              </div>
              <div className="flex-1">
                <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
                  Your Power Journey
                </h1>
                <p className="mt-1 text-slate-600">
                  Precision physics-based power estimation · ~3-5% accuracy
                </p>
              </div>
            </div>

            {/* Placeholder for Trends Analysis */}
            <div className="rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 p-8 text-center">
              <div className="text-slate-400 text-5xl mb-3">📊</div>
              <h3 className="text-lg font-semibold text-slate-700 mb-2">
                Upload rides to unlock your trends
              </h3>
              <p className="text-sm text-slate-600 max-w-md mx-auto">
                Import your last 50 rides and get an incredible analysis of your FTP progression, 
                W/kg improvements, and training insights over time.
              </p>
            </div>
          </div>
        </section>

        {/* 🎯 GOALS (Also launching April 1st) */}
        <section className="mb-6">
          <div className="rounded-3xl bg-white/95 backdrop-blur-sm p-6 shadow-[0_20px_60px_rgba(0,0,0,0.3)] relative overflow-hidden">
            
            {/* Lock overlay */}
            <div className="absolute inset-0 bg-gradient-to-br from-slate-900/5 to-slate-900/10 backdrop-blur-[2px] z-10 flex items-center justify-center">
              <div className="text-center">
                <div className="text-5xl mb-2">🔒</div>
                <div className="bg-white/90 backdrop-blur-sm rounded-xl px-4 py-2.5 shadow-lg">
                  <div className="text-sm font-bold text-slate-900">Launching April 1st</div>
                  <div className="text-xs text-slate-600 mt-0.5">Set training goals</div>
                </div>
              </div>
            </div>

            {/* Content (blurred) */}
            <div className="opacity-60">
              <div className="flex items-center gap-3 mb-4">
                <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-rose-400 to-rose-600 flex items-center justify-center text-white text-xl">
                  🎯
                </div>
                <h2 className="text-xl font-bold text-slate-900">Goals</h2>
              </div>

              <div className="rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 p-6 text-center">
                <div className="text-slate-400 text-3xl mb-2">+</div>
                <div className="text-sm font-semibold text-slate-700">
                  Set your first goal
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  Based on your trends
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* MAIN CONTENT - 2 Columns */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* LEFT: Import Rides */}
          <section className="rounded-3xl bg-white/95 backdrop-blur-sm p-6 shadow-[0_20px_60px_rgba(0,0,0,0.3)]">
            <div className="flex items-center gap-3 mb-4">
              <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white text-xl">
                🚴‍♂️
              </div>
              <h2 className="text-xl font-bold text-slate-900">Import Rides</h2>
            </div>
            <StravaImportCard />
          </section>

          {/* RIGHT: Leaderboards Teaser */}
          <section className="rounded-3xl bg-white/95 backdrop-blur-sm p-6 shadow-[0_20px_60px_rgba(0,0,0,0.3)] relative overflow-hidden">
            
            {/* Lock overlay */}
            <div className="absolute inset-0 bg-gradient-to-br from-slate-900/5 to-slate-900/10 backdrop-blur-[2px] z-10 flex items-center justify-center">
              <div className="text-center">
                <div className="text-5xl mb-2">🔒</div>
                <div className="bg-white/90 backdrop-blur-sm rounded-xl px-4 py-2.5 shadow-lg">
                  <div className="text-sm font-bold text-slate-900">Launching April 1st</div>
                  <div className="text-xs text-slate-600 mt-0.5">Compete & compare</div>
                </div>
              </div>
            </div>

            {/* Content (blurred) */}
            <div className="opacity-60">
              <div className="flex items-center gap-3 mb-4">
                <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center text-white text-xl">
                  🏆
                </div>
                <h2 className="text-xl font-bold text-slate-900">Leaderboards</h2>
              </div>

              <div className="space-y-3">
                <div className="text-xs font-semibold text-slate-500 uppercase">
                  Preview Rankings
                </div>

                <div className="rounded-xl border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-3 py-2 border-b border-slate-200">
                    <div className="text-xs font-medium text-slate-600">
                      📍 Your City · Age Group
                    </div>
                  </div>

                  {[1, 2, 3, '...', '?'].map((rank, idx) => (
                    <div
                      key={idx}
                      className="grid grid-cols-[30px_1fr_auto] gap-2 items-center px-3 py-2 border-b border-slate-200 last:border-b-0 bg-white"
                    >
                      <div className="text-sm font-bold text-slate-500">{rank}</div>
                      <div className="text-sm text-slate-400">███████</div>
                      <div className="text-sm font-semibold text-slate-400">
                        {rank === '?' ? '260 W' : '—'}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="text-xs text-slate-600 space-y-1">
                  <div>• 1min, 5min, 20min, 60min power</div>
                  <div>• Age, Gender, Location filters</div>
                  <div>• City & National rankings</div>
                </div>
              </div>
            </div>
          </section>

        </div>

        {/* PROFILE LINK */}
        <section className="mt-6">
          <Link
            to="/profile"
            className="block rounded-3xl bg-white/95 backdrop-blur-sm p-5 shadow-[0_20px_60px_rgba(0,0,0,0.3)] hover:bg-white transition-all group"
          >
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-purple-400 to-purple-600 flex items-center justify-center text-white text-2xl">
                👤
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-slate-900 group-hover:text-purple-700">
                  Profile Settings
                </h3>
                <p className="text-sm text-slate-600 group-hover:text-purple-600">
                  Manage your bike, weight, and connection settings
                </p>
              </div>
              <span className="text-slate-400 group-hover:text-purple-600 text-xl">→</span>
            </div>
          </Link>
        </section>

        {/* Footer */}
        <footer className="mt-12 text-center">
          <p className="text-white/70 text-sm">
            No power meter required · Physics-based precision
          </p>
        </footer>

      </div>
    </div>
  );
}
