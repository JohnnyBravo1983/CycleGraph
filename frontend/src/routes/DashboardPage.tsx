// frontend/src/routes/DashboardPage.tsx
import React from "react";
import { Link } from "react-router-dom";
import { cgApi } from "../lib/cgApi";
import { StravaImportCard } from "../components/StravaImportCard";
import { isDemoMode } from "../demo/demoMode";
import { demoRides, progressionSummary } from "../demo/demoRides";
import ProfileView from "../components/Profile/ProfileView";




// ✅ Patch 4a.2
import { leaderboardMockData } from "../demo/leaderboardMockData";

type YearKey = "2022" | "2023" | "2024" | "2025";

// ----------------------------
// Trend helpers (for tooltips)
// ----------------------------
type TrendPoint = {
  year: string;
  value: number;
  valueLabel: string;
  deltaLabel?: string;
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

function deltaStyle(sign?: TrendPoint["deltaSign"]) {
  if (sign === "pos") return "text-emerald-500";
  if (sign === "neg") return "text-red-500";
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
            <div className="absolute -top-2 left-3 h-3 w-3 rotate-45 border-l border-t border-slate-200 bg-white shadow-[0_4px_12px_rgba(0,0,0,0.08)]" />

            <div className="rounded-lg border border-slate-200 bg-white shadow-[0_4px_12px_rgba(0,0,0,0.15)] px-4 py-3 transition-opacity duration-200 ease-in-out text-slate-800">
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

// 🎨 NEW: Animated Mini FTP Preview Component
function AnimatedFTPPreview() {
  const ftpValues = [210, 225, 245, 260]; // 2022 → 2025
  const years = ['2022', '2023', '2024', '2025'];
  
  // SVG dimensions
  const width = 160;
  const height = 80;
  const padding = 15;
  
  // Calculate points
  const min = 200;
  const max = 270;
  const span = max - min;
  
  const points = ftpValues.map((val, idx) => ({
    x: padding + (idx * (width - padding * 2)) / (ftpValues.length - 1),
    y: padding + (1 - (val - min) / span) * (height - padding * 2),
    value: val,
    year: years[idx],
  }));
  
  // Build path
  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  
  return (
    <div className="flex justify-center mb-4">
      <div className="relative">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
          {/* Animated gradient path */}
          <defs>
            <linearGradient id="ftpGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="100%" stopColor="#059669" />
            </linearGradient>
          </defs>
          
          {/* Path with draw animation */}
          <path
            d={pathD}
            fill="none"
            stroke="url(#ftpGradient)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{
              strokeDasharray: 200,
              strokeDashoffset: 200,
              animation: 'drawPath 2s ease-out forwards',
            }}
          />
          
          {/* Animated dots */}
          {points.map((point, idx) => (
            <g key={idx}>
              {/* Outer ring */}
              <circle
                cx={point.x}
                cy={point.y}
                r="6"
                fill="none"
                stroke="#10b981"
                strokeWidth="2"
                opacity="0"
                style={{
                  animation: `popDot 0.4s ease-out ${0.5 + idx * 0.3}s forwards`,
                }}
              />
              {/* Inner dot */}
              <circle
                cx={point.x}
                cy={point.y}
                r="3"
                fill="#10b981"
                opacity="0"
                style={{
                  animation: `popDot 0.4s ease-out ${0.5 + idx * 0.3}s forwards`,
                }}
              />
            </g>
          ))}
        </svg>
        
        {/* Labels */}
        <div className="absolute -bottom-6 left-0 right-0 flex justify-between px-3 text-[10px] font-semibold text-emerald-700">
          <span>210W</span>
          <span>260W</span>
        </div>
        
        {/* Year labels */}
        <div className="absolute -top-5 left-0 right-0 flex justify-between px-3 text-[9px] text-slate-400">
          <span>'22</span>
          <span>'25</span>
        </div>
      </div>
      
      <style>{`
        @keyframes drawPath {
          to {
            stroke-dashoffset: 0;
          }
        }
        
        @keyframes popDot {
          0% {
            opacity: 0;
            transform: scale(0);
          }
          50% {
            opacity: 1;
            transform: scale(1.2);
          }
          100% {
            opacity: 1;
            transform: scale(1);
          }
        }
      `}</style>
    </div>
  );
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
          aiming for <span className="font-medium">~3–5% accuracy</span> in good conditions.
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
    const deltaKg = kgNow - kgPrev;
    const deltaWkgPct = wkgPrev !== 0 ? ((wkgNow - wkgPrev) / wkgPrev) * 100 : 0;

    computedDeltas[y] = { deltaFtpW, deltaFtpPct, deltaKg, deltaWkgPct };
  });

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
      <section className="flex items-center justify-between">
        <Link
          to="/"
          className="inline-flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-2 shadow-sm hover:bg-slate-50"
        >
          <img src="/CycleGraph_Logo.png" alt="CycleGraph" className="h-8 w-auto object-contain" />
          <span className="text-sm font-semibold text-slate-900">CycleGraph</span>
        </Link>
        <div className="text-xs text-slate-500">Demo dashboard</div>
      </section>

      <section className="mb-12">
        <div
          className="relative flex items-center gap-7 overflow-hidden rounded-2xl p-10 shadow-[0_12px_40px_rgba(102,126,234,0.40)] transition-transform duration-300 hover:-translate-y-1 hover:shadow-[0_16px_50px_rgba(102,126,234,0.50)] max-md:flex-col max-md:text-center max-md:p-8"
          style={{
            background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            color: "white",
          }}
        >
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(circle at top right, rgba(255,255,255,0.10) 0%, transparent 60%)",
            }}
          />
          <div className="relative z-10 flex-none text-6xl leading-none drop-shadow-[0_4px_12px_rgba(0,0,0,0.30)] max-md:text-5xl">
            ⚡
          </div>
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
    </div>
  );
};

// ========================================
// 🚀 DASHBOARD V6 FINAL - WITH ANIMATED PREVIEW + COUNTDOWN
// ========================================

export default function DashboardPage() {
  const demo = isDemoMode();

  // Countdown state for FTP trends banner
  const [timeLeft, setTimeLeft] = React.useState({
    days: 0,
    hours: 0,
    minutes: 0,
    seconds: 0
  });

  React.useEffect(() => {
    const targetDate = new Date('2026-03-01T00:00:00');
    
    const updateCountdown = () => {
      const now = new Date();
      const difference = targetDate - now;
      
      if (difference > 0) {
        setTimeLeft({
          days: Math.floor(difference / (1000 * 60 * 60 * 24)),
          hours: Math.floor((difference / (1000 * 60 * 60)) % 24),
          minutes: Math.floor((difference / 1000 / 60) % 60),
          seconds: Math.floor((difference / 1000) % 60)
        });
      }
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    
    return () => clearInterval(interval);
  }, []);

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

  return (
    <div 
      className="min-h-screen relative"
      style={{
        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
      }}
    >
      {/* Subtle noise texture */}
      <div 
        className="fixed inset-0 opacity-[0.015] pointer-events-none"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
        }}
      />

      <div className="max-w-4xl mx-auto px-4 py-6 relative">
        
        {/* HEADER */}
        <header className="flex items-center justify-between mb-6">
          <Link
            to="/"
            className="inline-flex items-center gap-2.5 rounded-xl border border-white/20 bg-white/10 backdrop-blur-md px-3.5 py-2 shadow-lg hover:bg-white/15 transition-all duration-200"
          >
            <img src="/CycleGraph_Logo.png" alt="CycleGraph" className="h-7 w-auto" />
            <span className="text-sm font-semibold text-white tracking-tight">CycleGraph</span>
          </Link>

          {/* ✅ PATCH 1.2: add "Profil" anchor link, keep /profile icon link unchanged */}
          <div className="flex items-center gap-3">
            <a
              href="#profile"
              className="px-3.5 py-2 rounded-xl border border-white/20 bg-white/10 backdrop-blur-md text-sm font-medium text-white shadow-lg hover:bg-white/15 transition-all duration-200"
              title="Gå til profilseksjon"
            >
              Profil
            </a>

            <Link
              to="/profile"
              className="group relative h-9 w-9 rounded-full bg-gradient-to-br from-white/20 to-white/5 backdrop-blur-md border border-white/30 flex items-center justify-center shadow-lg hover:scale-105 transition-transform duration-200"
              title="Profile Settings"
            >
              <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </Link>

            <button
              type="button"
              onClick={onLogout}
              className="px-3.5 py-2 rounded-xl border border-white/20 bg-white/10 backdrop-blur-md text-sm font-medium text-white shadow-lg hover:bg-white/15 transition-all duration-200"
            >
              Logg ut
            </button>
          </div>
        </header>

        <style>{`
          @keyframes slideUp {
            from {
              opacity: 0;
              transform: translateY(20px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }
          
          @keyframes shimmer {
            0% {
              background-position: -200% center;
            }
            100% {
              background-position: 200% center;
            }
          }
        `}</style>

        {/* 🔥 TRENDS HERO - WITH ANIMATED PREVIEW */}
        <section 
          className="mb-4"
          style={{
            animation: "slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1)",
          }}
        >
          <div className="rounded-2xl bg-white/98 backdrop-blur-xl p-8 shadow-[0_20px_60px_rgba(0,0,0,0.25)] border border-white/40 relative overflow-hidden">
            
            {/* Breakthrough Badge */}
            <div className="absolute top-4 right-4">
              <div 
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold tracking-wide shadow-lg"
                style={{
                  background: "linear-gradient(90deg, #fbbf24 0%, #f59e0b 50%, #fbbf24 100%)",
                  backgroundSize: "200% 100%",
                  animation: "shimmer 3s linear infinite",
                  color: "#78350f",
                }}
              >
                <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
                BREAKTHROUGH
              </div>
            </div>

            <div className="flex items-start gap-4 mb-6">
              <div className="flex-none">
                <div 
                  className="h-14 w-14 rounded-xl flex items-center justify-center shadow-lg relative overflow-hidden"
                  style={{
                    background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                  }}
                >
                  <svg className="h-7 w-7 text-white relative z-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                  <div className="absolute inset-0 bg-white/20" />
                </div>
              </div>
              <div className="flex-1 min-w-0 pr-24">
                <h1 className="text-2xl font-bold text-slate-900 tracking-tight leading-tight mb-1">
                  World-First Physics Power Trends
                </h1>
                <p className="text-sm text-slate-600 leading-relaxed">
                  First consumer app to deliver <span className="font-semibold text-emerald-600">~3-5% accuracy</span> power analysis without a power meter
                </p>
              </div>
            </div>

            {/* Value Prop Box - WITH ANIMATED PREVIEW */}
            <div className="rounded-xl border-2 border-emerald-100 bg-gradient-to-br from-emerald-50 to-white p-8 mb-6 relative overflow-hidden">
              {/* Subtle glow */}
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_120%,rgba(16,185,129,0.08),transparent_50%)]" />
              
              <div className="relative">
                {/* 🎨 ANIMATED FTP PREVIEW (replaces static icon) */}
                <AnimatedFTPPreview />

                {/* Value Props */}
                <div className="space-y-3 max-w-lg mx-auto">
                  <div className="flex items-start gap-3">
                    <div className="flex-none mt-0.5">
                      <svg className="h-5 w-5 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-900">Multi-year FTP progression</div>
                      <div className="text-xs text-slate-600 mt-0.5">Never been possible without a power meter before</div>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="flex-none mt-0.5">
                      <svg className="h-5 w-5 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-900">Full physics modeling</div>
                      <div className="text-xs text-slate-600 mt-0.5">Wind, air pressure, temperature, elevation - all modeled for precision</div>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="flex-none mt-0.5">
                      <svg className="h-5 w-5 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-900">Breakthrough accuracy</div>
                      <div className="text-xs text-slate-600 mt-0.5">Sanity tested to ~5% in good conditions - a consumer-app first</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 🎯 COMPACT COUNTDOWN BANNER */}
            <div className="bg-yellow-400 border-2 border-yellow-500 rounded-lg p-3 shadow-lg">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2 flex-1">
                  <span className="text-xl animate-pulse">⚡</span>
                  <div>
                    <p className="font-bold text-gray-800 text-sm">FTP Trend Analysis drops March 1st</p>
                    <p className="text-xs text-gray-700">
                      Your complete history appears automatically. <a href="/rides" className="underline font-semibold hover:text-gray-900">Check precision analysis →</a>
                    </p>
                  </div>
                </div>
                
                <div className="flex gap-2">
                  <div className="bg-white rounded px-2 py-1 min-w-[50px] text-center">
                    <div className="text-lg font-bold text-gray-800">{timeLeft.days}</div>
                    <div className="text-[10px] text-gray-600 uppercase">days</div>
                  </div>
                  <div className="bg-white rounded px-2 py-1 min-w-[50px] text-center">
                    <div className="text-lg font-bold text-gray-800">{timeLeft.hours}</div>
                    <div className="text-[10px] text-gray-600 uppercase">hrs</div>
                  </div>
                  <div className="bg-white rounded px-2 py-1 min-w-[50px] text-center">
                    <div className="text-lg font-bold text-gray-800 animate-pulse">{timeLeft.minutes}</div>
                    <div className="text-[10px] text-gray-600 uppercase">min</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 🎯 GOALS - Refined Lock */}
        <section 
          className="mb-4"
          style={{
            animation: "slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.1s backwards",
          }}
        >
          <div className="rounded-2xl bg-white/98 backdrop-blur-xl p-5 shadow-[0_20px_60px_rgba(0,0,0,0.25)] border border-white/40 relative overflow-hidden">
            
            <div className="absolute inset-0 bg-gradient-to-br from-slate-900/[0.03] via-slate-900/[0.02] to-transparent backdrop-blur-[1px] z-10 flex items-center justify-center">
              <div className="inline-flex items-center gap-2 bg-white/95 backdrop-blur-md rounded-full px-4 py-2 shadow-[0_8px_30px_rgba(0,0,0,0.12)] border border-slate-200/50">
                <svg className="h-4 w-4 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                <div className="text-xs font-semibold text-slate-900">Launching April 1st</div>
              </div>
            </div>




            <div className="opacity-40">
              <div className="flex items-center gap-3 mb-4">
                <div 
                  className="h-10 w-10 rounded-xl flex items-center justify-center shadow-md"
                  style={{
                    background: "linear-gradient(135deg, #f43f5e 0%, #e11d48 100%)",
                  }}
                >
                  <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                  </svg>
                </div>
                <h2 className="text-lg font-bold text-slate-900">Goals</h2>
              </div>

              <div className="rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 p-5 text-center">
                <svg className="h-8 w-8 mx-auto text-slate-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                <div className="text-sm font-semibold text-slate-700">Set your first goal</div>
                <div className="text-xs text-slate-500 mt-1">Based on your trends</div>
              </div>
            </div>
          </div>
        </section>

{/* PROFILE (read-only) */}
<section
  id="profile"
  className="mb-4 scroll-mt-24"
  style={{
    animation: "slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.15s backwards",
  }}
>
  <ProfileView />
</section>



        {/* TWO-COLUMN GRID */}
        <div 
          className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4"
          style={{
            animation: "slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.2s backwards",
          }}
        >
          
          {/* Import Rides */}
          <div className="rounded-2xl bg-white/98 backdrop-blur-xl p-5 shadow-[0_20px_60px_rgba(0,0,0,0.25)] border border-white/40">
            <div className="flex items-center gap-3 mb-4">
              <div 
                className="h-10 w-10 rounded-xl flex items-center justify-center shadow-md"
                style={{
                  background: "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)",
                }}
              >
                <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <h2 className="text-lg font-bold text-slate-900">Import Rides</h2>
            </div>
            <StravaImportCard />
          </div>

          {/* Leaderboards */}
          <div className="rounded-2xl bg-white/98 backdrop-blur-xl p-5 shadow-[0_20px_60px_rgba(0,0,0,0.25)] border border-white/40 relative overflow-hidden">
            
            <div className="absolute inset-0 bg-gradient-to-br from-slate-900/[0.03] via-slate-900/[0.02] to-transparent backdrop-blur-[1px] z-10 flex items-center justify-center">
              <div className="inline-flex items-center gap-2 bg-white/95 backdrop-blur-md rounded-full px-4 py-2 shadow-[0_8px_30px_rgba(0,0,0,0.12)] border border-slate-200/50">
                <svg className="h-4 w-4 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                <div className="text-xs font-semibold text-slate-900">April 1st</div>
              </div>
            </div>

            <div className="opacity-40">
              <div className="flex items-center gap-3 mb-4">
                <div 
                  className="h-10 w-10 rounded-xl flex items-center justify-center shadow-md"
                  style={{
                    background: "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
                  }}
                >
                  <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                  </svg>
                </div>
                <h2 className="text-lg font-bold text-slate-900">Leaderboards</h2>
              </div>

              <div className="space-y-2.5">
                <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Preview</div>

                <div className="rounded-lg border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-3 py-1.5 border-b border-slate-200">
                    <div className="text-[11px] font-medium text-slate-600">Your City · Age Group</div>
                  </div>

                  {[1, 2, 3, '...', '?'].map((rank, idx) => (
                    <div
                      key={idx}
                      className="grid grid-cols-[28px_1fr_auto] gap-2 items-center px-3 py-1.5 border-b border-slate-200 last:border-b-0 bg-white"
                    >
                      <div className="text-xs font-bold text-slate-500">{rank}</div>
                      <div className="text-xs text-slate-300">███████</div>
                      <div className="text-xs font-semibold text-slate-400">
                        {rank === '?' ? '260 W' : '—'}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="text-[11px] text-slate-500 space-y-0.5">
                  <div>• Power curves (1min, 5min, 20min, 60min)</div>
                  <div>• Age, Gender, Location filters</div>
                </div>
              </div>
            </div>
          </div>

        </div>

        {/* Footer */}
        <footer className="mt-6 text-center">
          <p className="text-white/60 text-xs font-medium tracking-wide">
            World's first physics-based power trends · No hardware required
          </p>
        </footer>

      </div>
    </div>
  );
}
