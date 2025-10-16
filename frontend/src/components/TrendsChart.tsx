// frontend/src/components/TrendsChart.tsx
import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { getBackendBase, fetchJSON } from "../lib/fetchJSON";

export interface TrendsChartProps {
  sessionId: string; // brukes til å ev. highlight'e aktuell økt
  isMock: boolean;

  /** Valgfritt: brukes for HR-only autodeteksjon i denne komponenten */
  series?: { t: number[]; watts?: number[]; hr?: number[] };
  /** Valgfritt: eksplisitt HR-only flagg; overstyrer auto */
  hrOnly?: boolean;
  /** Valgfritt: ikke brukt i tegning her, men aksepteres for kompatibilitet */
  calibrated?: boolean | null;
  /** Valgfritt: ikke brukt i tegning her, men aksepteres for kompatibilitet */
  source?: "API" | "Mock" | string;
}

type TrendPoint = {
  id: string;
  timestamp: number; // ms epoch
  np?: number | null;
  pw?: number | null;
  source?: "API" | "Mock" | string;
  calibrated?: boolean;
};

type FetchState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; data: TrendPoint[] }
  | { kind: "error"; message: string };

const W = 820;
const H = 320;

const PLOT_X = 50;
// keep file stable for tailwind jit; comment only, not a label
const PLOT_Y = 16;
const PLOT_W = 752;
const PLOT_H = 276;
const PLOT_RIGHT = PLOT_X + PLOT_W;
const PLOT_BOTTOM = PLOT_Y + PLOT_H;

/** Trygg uthenting av runtime-modus uten å knekke i Vitest/Node */
function getRuntimeMode(): string {
  let viteMode: string | undefined;
  try {
    viteMode =
      (typeof import.meta !== "undefined" &&
        (import.meta as unknown as { env?: Record<string, string | undefined> }).env?.MODE) ||
      undefined;
  } catch {
    /* noop */
  }
  const nodeMode = typeof process !== "undefined" ? process.env?.NODE_ENV : undefined;
  return (viteMode || nodeMode || "production").toLowerCase();
}

/** Sann i vitest (MODE='test' eller globalThis.vitest satt) – uten `any` */
function isTestEnv(): boolean {
  if (getRuntimeMode() === "test") return true;
  if (typeof globalThis !== "undefined") {
    const maybeVitest = (globalThis as unknown as Record<string, unknown>).vitest;
    return typeof maybeVitest !== "undefined";
  }
  return false;
}

/** Les VITE_USE_MOCK trygt (kan mangle i test) */
function isMockEnv(): boolean {
  try {
    const env = (import.meta as unknown as { env?: Record<string, string | undefined> }).env;
    return (env?.VITE_USE_MOCK ?? "").toLowerCase() === "true";
  } catch {
    return false;
  }
}

/** Les VITE_USE_LIVE_TRENDS trygt (kan mangle i test) */
function isLiveTrendsEnv(): boolean {
  try {
    const env = (import.meta as unknown as { env?: Record<string, string | undefined> }).env;
    return (env?.VITE_USE_LIVE_TRENDS ?? "").toLowerCase() === "true";
  } catch {
    return false;
  }
}

function niceNum(n: number) {
  return Number.isFinite(n) ? Math.round(n) : n;
}

function formatDate(ts: number) {
  const d = new Date(ts);
  return d.toLocaleString(undefined, {
    year: "2-digit",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function linePath(xs: number[], ys: number[]) {
  let d = "";
  for (let i = 0; i < xs.length; i++) {
    const cmd = i === 0 ? "M" : "L";
    d += `${cmd}${xs[i]},${ys[i]}`;
  }
  return d;
}

function binarySearchClosestIndex(xs: number[], x: number): number {
  let lo = 0;
  let hi = xs.length - 1;
  if (xs.length === 0) return -1;
  if (x <= xs[0]) return 0;
  if (x >= xs[hi]) return hi;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const v = xs[mid];
    if (v === x) return mid;
    if (v < x) lo = mid + 1;
    else hi = mid - 1;
  }
  const i1 = Math.max(0, lo - 1);
  const i2 = Math.min(xs.length - 1, lo);
  return Math.abs(xs[i1] - x) <= Math.abs(xs[i2] - x) ? i1 : i2;
}

export default function TrendsChart(props: TrendsChartProps) {
  const { sessionId, isMock } = props;

  // 1) Hooks må kalles ubetinget og i fast rekkefølge
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hover, setHover] = useState<{ x: number; y: number } | null>(null);
  const [state, setState] = useState<FetchState>({ kind: "idle" });

  // 2) Utledninger (useMemo) – fortsatt ubetinget
  const autoHrOnly = useMemo(() => {
    const hrLen = props.series?.hr?.length ?? 0;
    const wLen = props.series?.watts?.length ?? 0;
    return hrLen > 0 && wLen === 0;
  }, [props.series?.hr?.length, props.series?.watts?.length]);

  const computedHrOnly = props.hrOnly ?? autoHrOnly ?? false;

  // 3) Datafetch – aldri skippe hook-kallet; skip handling INNI effekten
  useEffect(() => {
    let cancelled = false;
    const TIMEOUT_MS = 5000; // 5s: unngå evig "Laster…"
    const controller = new AbortController();
    const timer = setTimeout(() => {
      if (!controller.signal.aborted) controller.abort();
    }, TIMEOUT_MS);
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    function buildHrOnlyFallbackData(): TrendPoint[] {
      const now = Date.now();
      // 5 punkter med np/pw = null for å trigge "Ingen wattdata tilgjengelig"
      return Array.from({ length: 5 }).map((_, i) => ({
        id: `hronly-${i}`,
        timestamp: now - (5 - i) * 24 * 3600 * 1000,
        np: null,
        pw: null,
        source: "API",
        calibrated: false,
      }));
    }

    async function run() {
      // HR-only: ikke hent trendgraf – men behold hook-rekkefølge
      if (computedHrOnly) {
        setState((prev) => (prev.kind === "loaded" ? prev : { kind: "idle" }));
        return;
      }

      // Veksle mellom live og mock etter env/prop (i test skal prop styre)
      const liveActive = isLiveTrendsEnv();
      const mockActive = isMock || (!isTestEnv() && isMockEnv());

      // MOCK: generer deterministiske punkter
      if (!liveActive || mockActive) {
        const now = Date.now();
        const pts: TrendPoint[] = Array.from({ length: 30 }).map((_, i) => {
          const ts = now - (30 - i) * 2 * 24 * 3600 * 1000;
          const hasPower = i % 7 !== 3; // noen HR-only punkter i historikken
          const np = hasPower ? Math.round(220 + Math.sin(i / 2) * 20 + (i % 5) * 2) : null;
          const pw = hasPower ? Math.round(210 + Math.cos(i / 3) * 18 + (i % 3) * 3) : null;
          return {
            id: `mock-${i}`,
            timestamp: ts,
            np,
            pw,
            source: "Mock",
            calibrated: i % 4 !== 0,
          };
        });
        if (!cancelled) setState({ kind: "loaded", data: pts });
        return;
      }

      setState({ kind: "loading" });

      // Live: hent fra /api/trends?from&to&bucket=day via fetchJSON()
      const base = getBackendBase(); // '' i dev (Vite-proxy), ellers absolutt URL
      const params = new URLSearchParams();
      // Kravet sier from&to&bucket=day; vi setter bare bucket nå (from/to kan legges til senere)
      params.set("bucket", "day");
      const pathTrends = `/api/trends?${params.toString()}`;
      const url = base ? `${base.replace(/\/+$/, "")}${pathTrends}` : pathTrends;

      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      type TrendApiRow = {
        id?: string | number;
        session_id?: string | number;
        timestamp?: number | string;
        ts?: number | string;
        np?: number | null;
        pw?: number | null;
        source?: "API" | "Mock" | string;
        calibrated?: boolean;
      };

      try {
        const raw = await fetchJSON<unknown>(url, { signal: controller.signal });

        let rows: TrendPoint[] | null = null;

        if (Array.isArray(raw)) {
          const arr = raw as Array<Record<string, unknown>>;
          rows = arr.map((r) => {
            const idVal = r.id ?? r.session_id ?? "";
            const tsv = r.timestamp ?? r.ts ?? 0;
            const ts = typeof tsv === "string" ? Number(tsv) : (tsv as number);
            return {
              id: String(idVal),
              timestamp: Number(ts),
              np: (r.np as number | null | undefined) ?? null,
              pw: (r.pw as number | null | undefined) ?? null,
              source: (r.source as string | undefined) ?? "API",
              calibrated: Boolean(r.calibrated),
            };
          });
        } else if (typeof raw === "object" && raw !== null) {
          // Eldre mock-objekt { t, watts, hr }
          if (Array.isArray((raw as { t?: unknown }).t)) {
            const r2 = raw as { t: number[]; watts?: number[]; hr?: number[] };
            rows = r2.t.map((tVal, i) => ({
              id: `legacy-${i}`,
              timestamp: Number(tVal),
              np: r2.watts?.[i] ?? null,
              pw: r2.watts?.[i] ?? null,
              source: "Mock",
              calibrated: false,
            }));
          }
          // Objekt med { sessions: [...] }
          else if (Array.isArray((raw as { sessions?: unknown[] }).sessions)) {
            const arr = (raw as { sessions: Array<Record<string, unknown>> }).sessions;
            rows = arr.map((r, i) => ({
              id: String(r.id ?? `sum-${i}`),
              timestamp: Number(
                (r.timestamp as number | string | undefined) ??
                  Date.now() - (arr.length - i) * 86400000
              ),
              np: (r.np as number | null | undefined) ?? null,
              pw: (r.pw as number | null | undefined) ?? null,
              source: "API",
              calibrated: Boolean(r.calibrated),
            }));
          }
        }

        if (!cancelled) {
          setState({ kind: "loaded", data: rows ?? [] });
        }
      } catch (e) {
        // Stille ignorering av AbortError (ingen logging)
        if (e instanceof DOMException && e.name === "AbortError") {
          // ikke oppdater state hvis vi allerede unmountet
          if (!cancelled) setState((prev) => (prev.kind === "loaded" ? prev : { kind: "idle" }));
          return;
        }
        // Andre feil: ikke spam konsoll; vis en kort feilmelding i UI (ikke crash)
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : String(e);
          setState({
            kind: "error",
            message: /abort/i.test(msg) ? "Tidsavbrudd ved henting av trenddata." : msg,
          });
        }
      }
    }

    run();

    return () => {
      cancelled = true;
      clearTimeout(timer);
      if (!controller.signal.aborted) controller.abort();
    };
  }, [isMock, computedHrOnly, sessionId]);

  // 4) Avledet data – hooks fortsatt før noen returns
  const data: TrendPoint[] = useMemo(
    () => (state.kind === "loaded" ? state.data : []),
    [state]
  );

  const sortedData: TrendPoint[] = useMemo(() => {
    if (data.length === 0) return [];
    const copy = data.slice();
    copy.sort((a, b) => a.timestamp - b.timestamp);
    return copy;
  }, [data]);

  const xDomain = useMemo(() => {
    if (sortedData.length === 0) return [0, 1] as const;
    return [sortedData[0].timestamp, sortedData[sortedData.length - 1].timestamp] as const;
  }, [sortedData]);

  const yDomain = useMemo(() => {
    let lo = Infinity;
    let hi = -Infinity;
    for (const d of sortedData) {
      if (typeof d.np === "number") {
        lo = Math.min(lo, d.np);
        hi = Math.max(hi, d.np);
      }
      if (typeof d.pw === "number") {
        lo = Math.min(lo, d.pw);
        hi = Math.max(hi, d.pw);
      }
    }
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) {
      return [0, 1] as const;
    }
    const pad = Math.max(5, (hi - lo) * 0.1);
    return [Math.max(0, lo - pad), hi + pad] as const;
  }, [sortedData]);

  const haveAnyPower = useMemo(
    () => sortedData.some((d) => typeof d.np === "number" || typeof d.pw === "number"),
    [sortedData]
  );

  const xScale = useCallback(
    (ts: number) => {
      const [x0, x1] = xDomain;
      if (x1 === x0) return PLOT_X;
      const t = (ts - x0) / (x1 - x0);
      return PLOT_X + t * PLOT_W;
    },
    [xDomain]
  );

  const yScale = useCallback(
    (v: number) => {
      const [y0, y1] = yDomain;
      if (y1 === y0) return PLOT_BOTTOM;
      const t = (v - y0) / (y1 - y0);
      return PLOT_BOTTOM - t * PLOT_H;
    },
    [yDomain]
  );

  const seriesNP = useMemo(
    () => sortedData.filter((d) => typeof d.np === "number"),
    [sortedData]
  );
  const seriesPW = useMemo(
    () => sortedData.filter((d) => typeof d.pw === "number"),
    [sortedData]
  );

  const npPath = useMemo(() => {
    if (seriesNP.length === 0) return "";
    const xs = seriesNP.map((d) => xScale(d.timestamp));
    const ys = seriesNP.map((d) => yScale(d.np as number));
    return linePath(xs, ys);
  }, [seriesNP, xScale, yScale]);

  const pwPath = useMemo(() => {
    if (seriesPW.length === 0) return "";
    const xs = seriesPW.map((d) => xScale(d.timestamp));
    const ys = seriesPW.map((d) => yScale(d.pw as number));
    return linePath(xs, ys);
  }, [seriesPW, xScale, yScale]);

  const xPixels = useMemo(() => sortedData.map((d) => xScale(d.timestamp)), [sortedData, xScale]);

  const handlePointerMove = useCallback((e: React.PointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setHover({ x, y });
  }, []);

  const handlePointerLeave = useCallback(() => setHover(null), []);

  const hoverIdx = useMemo(() => {
    if (!hover || xPixels.length === 0) return -1;
    const clampedX = Math.max(PLOT_X, Math.min(PLOT_RIGHT, hover.x));
    return binarySearchClosestIndex(xPixels, clampedX);
  }, [hover, xPixels]);

  const hoverPoint = hoverIdx >= 0 ? sortedData[hoverIdx] : null;

  // Hooks som må komme før tidlige return (for å tilfredsstille eslint/react)
  const xTicks = useMemo(() => {
    if (sortedData.length < 2) return [];
    const n = Math.min(6, Math.max(2, Math.floor(PLOT_W / 140)));
    const [x0, x1] = xDomain;
    return Array.from({ length: n }).map((_, i) => {
      const t = i / (n - 1);
      const ts = x0 + t * (x1 - x0);
      return { x: xScale(ts), label: new Date(ts).toLocaleDateString() };
    });
  }, [sortedData.length, xDomain, xScale]);

  const yTicks = useMemo(() => {
    const [y0, y1] = yDomain;
    const n = Math.min(6, Math.max(2, Math.floor(PLOT_H / 60)));
    return Array.from({ length: n }).map((_, i) => {
      const t = i / (n - 1);
      const v = y0 + t * (y1 - y0);
      return { y: yScale(v), label: `${Math.round(v)}` };
    });
  }, [yDomain, yScale]);

  // 5) Nå kan vi returnere basert på tilstand — hooks er allerede kalt
  if (computedHrOnly) {
    return (
      <div className="w-full rounded-xl border border-slate-200 bg-slate-50 p-6 text-slate-600">
        <p className="text-sm">
          Denne økten inneholder bare pulsdata (ingen wattmåler). Vi skjuler
          watt-trendgrafen, men viser fortsatt analyse og trender basert på puls der det er relevant.
        </p>
      </div>
    );
  }

  if (state.kind === "loading") {
    return <div className="text-sm text-slate-500">Laster trenddata…</div>;
  }
  if (state.kind === "error") {
    return (
      <div role="alert" className="text-sm text-red-600">
        Kunne ikke laste trenddata: {state.message}
      </div>
    );
  }
  if (state.kind === "loaded" && sortedData.length === 0) {
    // Krav: "Hvis data.length === 0, vis en 'Ingen data ennå'-melding"
    return <div className="text-sm text-slate-500">Ingen data ennå</div>;
  }
  if (state.kind === "loaded" && !haveAnyPower) {
    return <div className="text-sm text-slate-500">Ingen wattdata tilgjengelig</div>;
  }

  return (
    <div className="w-full overflow-x-auto">
      <div className="text-sm mb-2 font-medium">Trender: NP vs PW</div>
      <svg
        ref={svgRef}
        width={W}
        height={H}
        role="img"
        aria-label="Trends NP og PW"
        className="bg-white rounded-xl shadow-sm"
        onPointerMove={handlePointerMove}
        onPointerLeave={handlePointerLeave}
      >
        {/* plot bg */}
        <rect x={PLOT_X} y={PLOT_Y} width={PLOT_W} height={PLOT_H} className="fill-white" />

        {/* grid Y */}
        {yTicks.map((t, i) => (
          <line key={`gy-${i}`} x1={PLOT_X} x2={PLOT_RIGHT} y1={t.y} y2={t.y} className="stroke-slate-100" />
        ))}

        {/* grid X */}
        {xTicks.map((t, i) => (
          <line key={`gx-${i}`} x1={t.x} x2={t.x} y1={PLOT_Y} y2={PLOT_BOTTOM} className="stroke-slate-100" />
        ))}

        {/* axes */}
        <line x1={PLOT_X} x2={PLOT_RIGHT} y1={PLOT_BOTTOM} y2={PLOT_BOTTOM} className="stroke-slate-300" />
        <line x1={PLOT_X} x2={PLOT_X} y1={PLOT_Y} y2={PLOT_BOTTOM} className="stroke-slate-300" />

        {/* y labels */}
        {yTicks.map((t, i) => (
          <text
            key={`yl-${i}`}
            x={PLOT_X - 8}
            y={t.y}
            textAnchor="end"
            dominantBaseline="middle"
            className="fill-slate-500 text-xs"
          >
            {t.label}
          </text>
        ))}

        {/* x labels */}
        {xTicks.map((t, i) => (
          <text
            key={`xl-${i}`}
            x={t.x}
            y={PLOT_BOTTOM + 12}
            textAnchor="middle"
            dominantBaseline="hanging"
            className="fill-slate-500 text-[10px]"
          >
            {t.label}
          </text>
        ))}

        {/* NP path (blå) */}
        {npPath && <path d={npPath} className="stroke-blue-500 fill-none" strokeWidth={2} />}

        {/* PW path (grønn) */}
        {pwPath && <path d={pwPath} className="stroke-green-500 fill-none" strokeWidth={2} />}

        {/* Points */}
        {seriesNP.map((d) => (
          <circle key={`np-${d.id}`} cx={xScale(d.timestamp)} cy={yScale(d.np as number)} r={2} className="fill-blue-500" />
        ))}
        {seriesPW.map((d) => (
          <circle key={`pw-${d.id}`} cx={xScale(d.timestamp)} cy={yScale(d.pw as number)} r={2} className="fill-green-500" />
        ))}

        {/* Highlight current session */}
        {sortedData.some((d) => d.id === sessionId) && (
          <circle
            cx={xScale(sortedData.find((d) => d.id === sessionId)!.timestamp)}
            cy={(() => {
              const d = sortedData.find((x) => x.id === sessionId)!;
              const yVal = typeof d.pw === "number" ? d.pw : typeof d.np === "number" ? d.np : yDomain[0];
              return yScale(yVal as number);
            })()}
            r={4}
            className="fill-amber-500"
          />
        )}

        {/* Hover crosshair */}
        {hover && (
          <>
            <line x1={hover.x} x2={hover.x} y1={PLOT_Y} y2={PLOT_BOTTOM} className="stroke-slate-200" />
            <line x1={PLOT_X} x2={PLOT_RIGHT} y1={hover.y} y2={hover.y} className="stroke-slate-200" />
          </>
        )}

        {/* Tooltip */}
        {hoverPoint && (
          <g>
            <rect
              x={Math.min(PLOT_RIGHT - 180, Math.max(PLOT_X, xScale(hoverPoint.timestamp) + 8))}
              y={PLOT_Y + 8}
              width={170}
              height={74}
              rx={8}
              className="fill-white stroke-slate-200"
            />
            <text
              x={Math.min(PLOT_RIGHT - 170, Math.max(PLOT_X + 10, xScale(hoverPoint.timestamp) + 18))}
              y={PLOT_Y + 24}
              className="fill-slate-700 text-xs"
            >
              {formatDate(hoverPoint.timestamp)}
            </text>
            <text
              x={Math.min(PLOT_RIGHT - 170, Math.max(PLOT_X + 10, xScale(hoverPoint.timestamp) + 18))}
              y={PLOT_Y + 40}
              className="fill-blue-600 text-xs"
            >
              NP: {typeof hoverPoint.np === "number" ? `${niceNum(hoverPoint.np)} W` : "—"}
            </text>
            <text
              x={Math.min(PLOT_RIGHT - 170, Math.max(PLOT_X + 10, xScale(hoverPoint.timestamp) + 18))}
              y={PLOT_Y + 56}
              className="fill-green-600 text-xs"
            >
              PW: {typeof hoverPoint.pw === "number" ? `${niceNum(hoverPoint.pw)} W` : "—"}
            </text>
            <text
              x={Math.min(PLOT_RIGHT - 170, Math.max(PLOT_X + 10, xScale(hoverPoint.timestamp) + 18))}
              y={PLOT_Y + 72}
              className="fill-slate-500 text-[10px]"
            >
              Kilde: {String(hoverPoint.source ?? (isMock ? "Mock" : "API"))} • Kalibrert:{" "}
              {hoverPoint.calibrated ? "Ja" : "Nei"}
            </text>
          </g>
        )}

        {/* Legend */}
        <g aria-label="legend">
          <circle cx={PLOT_X + 8} cy={PLOT_Y + 8} r={4} className="fill-blue-500" />
          <text x={PLOT_X + 18} y={PLOT_Y + 8} dominantBaseline="middle" className="fill-slate-700 text-xs">
            NP
          </text>

          <circle cx={PLOT_X + 52} cy={PLOT_Y + 8} r={4} className="fill-green-500" />
          <text x={PLOT_X + 62} y={PLOT_Y + 8} dominantBaseline="middle" className="fill-slate-700 text-xs">
            PW
          </text>

          {!haveAnyPower && (
            <text x={PLOT_X + 100} y={PLOT_Y + 8} dominantBaseline="middle" className="fill-slate-500 text-xs">
              HR-only
            </text>
          )}
        </g>
      </svg>
    </div>
  );
}
