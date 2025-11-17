import React, {
  useEffect,
  useMemo,
  useRef,
  useState,
  useCallback,
} from "react";
import { getTrendSummary, getTrendPivot } from "../lib/api";
import { mapSummaryCsvToSeries } from "../lib/series";

export interface TrendsChartProps {
  sessionId: string;
  isMock: boolean;
  series?: { t: number[]; watts?: number[]; hr?: number[] };
  hrOnly?: boolean;
  calibrated?: boolean | null;
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
const PLOT_Y = 16;
const PLOT_W = 752;
const PLOT_H = 276;
const PLOT_RIGHT = PLOT_X + PLOT_W;
const PLOT_BOTTOM = PLOT_Y + PLOT_H;

function getRuntimeMode(): string {
  let viteMode: string | undefined;
  try {
    viteMode =
      (typeof import.meta !== "undefined" &&
        (import.meta as unknown as { env?: Record<string, string | undefined> })
          .env?.MODE) ||
      undefined;
  } catch {
    // Ikke-kritisk: env kan mangle i test/build-miljø
    void 0;
  }
  const nodeMode =
    typeof process !== "undefined" ? process.env?.NODE_ENV : undefined;
  return (viteMode || nodeMode || "production").toLowerCase();
}
function isTestEnv(): boolean {
  if (getRuntimeMode() === "test") return true;
  if (typeof globalThis !== "undefined") {
    const maybeVitest = (globalThis as unknown as Record<string, unknown>)
      .vitest;
    return typeof maybeVitest !== "undefined";
  }
  return false;
}
function isMockEnv(): boolean {
  try {
    const env = (import.meta as unknown as { env?: Record<string, string | undefined> })
      .env;
    return (env?.VITE_USE_MOCK ?? "").toLowerCase() === "true";
  } catch {
    return false;
  }
}
function isLiveTrendsEnv(): boolean {
  try {
    const env = (import.meta as unknown as { env?: Record<string, string | undefined> })
      .env;
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
  for (let i = 0; i < xs.length; i++)
    d += `${i === 0 ? "M" : "L"}${xs[i]},${ys[i]}`;
  return d;
}
function binarySearchClosestIndex(xs: number[], x: number): number {
  let lo = 0,
    hi = xs.length - 1;
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

// --- Performance helpers: mobil-nedprøving ---
const isMobileViewport = () => {
  if (typeof window === "undefined") return false;
  if (typeof window.matchMedia !== "function") return false;
  return window.matchMedia("(max-width: 768px)").matches;
};

function sampleEveryN<T>(arr: T[], n: number): T[] {
  if (!Array.isArray(arr) || n <= 1) return arr;
  const out: T[] = [];
  for (let i = 0; i < arr.length; i += n) out.push(arr[i]);
  return out;
}

export default function TrendsChart(props: TrendsChartProps) {
  const { sessionId, isMock } = props;

  // 1) Hooks
  const svgRef = useRef<SVGSVGElement | null>(null);
  const rafRef = useRef<number | null>(null);
  const [hover, setHover] = useState<{ x: number; y: number } | null>(null);
  const [state, setState] = useState<FetchState>({ kind: "idle" });
  const [hasPivot, setHasPivot] = useState<boolean>(false);

  // 2) Utledninger
  const autoHrOnly = useMemo(() => {
    const hrLen = props.series?.hr?.length ?? 0;
    const wLen = props.series?.watts?.length ?? 0;
    return hrLen > 0 && wLen === 0;
  }, [props.series?.hr?.length, props.series?.watts?.length]);
  const computedHrOnly = props.hrOnly ?? autoHrOnly ?? false;

  // 3) Datafetch – nå via getTrendSummary() / getTrendPivot()
  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (computedHrOnly) {
        setState((p) => (p.kind === "loaded" ? p : { kind: "idle" }));
        setHasPivot(false);
        return;
      }

      const testEnv = isTestEnv();
      const liveActive = isLiveTrendsEnv();
      const mockActive = isMock || (!testEnv && isMockEnv());

      // I ikke-testmiljø: bruk mock når live ikke er aktiv eller mock er eksplisitt på.
      if (!testEnv && (mockActive || !liveActive)) {
        const now = Date.now();
        const pts: TrendPoint[] = Array.from({ length: 30 }).map((_, i) => {
          const ts = now - (30 - i) * 2 * 24 * 3600 * 1000;
          const hasPower = i % 7 !== 3;
          const np = hasPower
            ? Math.round(220 + Math.sin(i / 2) * 20 + (i % 5) * 2)
            : null;
          const pw = hasPower
            ? Math.round(210 + Math.cos(i / 3) * 18 + (i % 3) * 3)
            : null;
          return {
            id: `mock-${i}`,
            timestamp: ts,
            np,
            pw,
            source: "Mock",
            calibrated: i % 4 !== 0,
          };
        });
        if (!cancelled) {
          setState({ kind: "loaded", data: pts });
          setHasPivot(false);
        }
        return;
      }

      // Test og "ekte" live: bruk backend-trendendepunkter via api.ts
      setState({ kind: "loading" });
      setHasPivot(false);

      try {
        const summary = await getTrendSummary();

        if (!summary || !summary.rows || summary.rows.length <= 1) {
          if (!cancelled) {
            setState({ kind: "loaded", data: [] });
            setHasPivot(false);
          }
          return;
        }

        // Bygg NP og PW fra summary.csv
        const avgSeries = mapSummaryCsvToSeries(summary.rows, "avg_watt");
        const wPerBeatSeries = mapSummaryCsvToSeries(
          summary.rows,
          "w_per_beat"
        );

        const rows: TrendPoint[] = avgSeries.map((p, idx) => {
          const twin = wPerBeatSeries[idx];
          const ts =
            p.x instanceof Date
              ? p.x.getTime()
              : new Date(String(p.x)).getTime();

          return {
            id: `trend-${idx}`,
            timestamp: ts,
            np: typeof p.y === "number" ? p.y : null,
            pw:
              twin && typeof twin.y === "number"
                ? twin.y
                : null,
            source: "API",
            calibrated: true,
          };
        });

        if (!cancelled) {
          setState({ kind: "loaded", data: rows });
        }

        // TODO S16: koble på faktisk profile_version her i stedet for 0
        const pivot = await getTrendPivot("avg_watt", 0);
        if (!cancelled) {
          if (pivot && pivot.rows && pivot.rows.length > 1) {
            setHasPivot(true);
          } else {
            setHasPivot(false);
          }
        }
      } catch (e) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : String(e);
          setState({
            kind: "error",
            message: /abort/i.test(msg)
              ? "Tidsavbrudd ved henting av trenddata."
              : msg,
          });
          setHasPivot(false);
        }
      }
    }

    void run();

    return () => {
      cancelled = true;
    };
  }, [isMock, computedHrOnly, sessionId]);

  // 4) Avledet data + mobil-nedprøving og memo
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

  const downsampled: TrendPoint[] = useMemo(() => {
    if (!isMobileViewport()) return sortedData;
    return sampleEveryN(sortedData, 6);
  }, [sortedData]);

  const xDomain = useMemo(() => {
    if (downsampled.length === 0) return [0, 1] as const;
    return [
      downsampled[0].timestamp,
      downsampled[downsampled.length - 1].timestamp,
    ] as const;
  }, [downsampled]);

  const yDomain = useMemo(() => {
    let lo = Infinity,
      hi = -Infinity;
    for (const d of downsampled) {
      if (typeof d.np === "number") {
        lo = Math.min(lo, d.np);
        hi = Math.max(hi, d.np);
      }
      if (typeof d.pw === "number") {
        lo = Math.min(lo, d.pw);
        hi = Math.max(hi, d.pw);
      }
    }
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [0, 1] as const;
    const pad = Math.max(5, (hi - lo) * 0.1);
    return [Math.max(0, lo - pad), hi + pad] as const;
  }, [downsampled]);

  const haveAnyPower = useMemo(
    () =>
      downsampled.some(
        (d) => typeof d.np === "number" || typeof d.pw === "number"
      ),
    [downsampled]
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
    () => downsampled.filter((d) => typeof d.np === "number"),
    [downsampled]
  );
  const seriesPW = useMemo(
    () => downsampled.filter((d) => typeof d.pw === "number"),
    [downsampled]
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

  const xPixels = useMemo(
    () => downsampled.map((d) => xScale(d.timestamp)),
    [downsampled, xScale]
  );

  // rAF-throttle på pointermove (lavere TBT) + fallback hvis rAF mangler
  const handlePointerMove = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      if (typeof requestAnimationFrame === "function") {
        if (rafRef.current) cancelAnimationFrame(rafRef.current);
        rafRef.current = requestAnimationFrame(() => setHover({ x, y }));
      } else {
        setHover({ x, y });
      }
    },
    []
  );
  const handlePointerLeave = useCallback(() => setHover(null), []);

  const hoverIdx = useMemo(() => {
    if (!hover || xPixels.length === 0) return -1;
    const clampedX = Math.max(PLOT_X, Math.min(PLOT_RIGHT, hover.x));
    return binarySearchClosestIndex(xPixels, clampedX);
  }, [hover, xPixels]);

  const hoverPoint = hoverIdx >= 0 ? downsampled[hoverIdx] : null;

  // 5) Render: alltid wrapper + tittel + SVG (også i tom/HR-only)
  // velg placeholder-melding
  let placeholderText: string | null = null;
  if (computedHrOnly) {
    placeholderText =
      "Denne økten har bare pulsdata (ingen wattmåler). Watt-trendgrafen er ikke tilgjengelig.";
  } else if (state.kind === "loading" || state.kind === "idle") {
    placeholderText = "Laster trenddata…";
  } else if (state.kind === "error") {
    placeholderText = `Kunne ikke laste trenddata: ${state.message}`;
  } else if (state.kind === "loaded" && downsampled.length === 0) {
    placeholderText = "Ingen data ennå";
  } else if (state.kind === "loaded" && !haveAnyPower) {
    placeholderText = "Ingen wattdata tilgjengelig";
  }

  const showPlot = placeholderText === null;

  return (
    <div className="w-full">
      <div className="text-sm mb-2 font-medium">Trender: NP vs PW</div>

      {/* Skjulte hjelpenoder for tester (Trinn 3 DoD) */}
      {state.kind === "loaded" && downsampled.length === 0 && (
        <div data-testid="trend-empty" className="hidden">
          No trend data available
        </div>
      )}

      {state.kind === "loaded" && downsampled.length > 0 && (
        <ul data-testid="trend-summary" className="hidden">
          {sortedData.map((d) => (
            <li key={d.id}>
              {new Date(d.timestamp).toISOString().slice(0, 10)} –{" "}
              {typeof d.np === "number" ? d.np.toFixed(1) : "–"}
            </li>
          ))}
        </ul>
      )}

      {hasPivot && (
        <div data-testid="trend-pivot" className="hidden">
          pivot-data
        </div>
      )}

      <svg
        ref={svgRef}
        width={W}
        height={H}
        role="img"
        aria-label="Trends NP og PW"
        className="bg-white rounded-xl shadow-sm"
        onPointerMove={showPlot ? handlePointerMove : undefined}
        onPointerLeave={showPlot ? handlePointerLeave : undefined}
      >
        {/* plot bg */}
        <rect
          x={PLOT_X}
          y={PLOT_Y}
          width={PLOT_W}
          height={PLOT_H}
          className="fill-white"
        />

        {/* grid + akser tegnes kun når vi faktisk viser plot */}
        {showPlot ? (
          <>
            {/* grid Y */}
            {(() => {
              const [y0, y1] = yDomain;
              const n = Math.min(6, Math.max(2, Math.floor(PLOT_H / 60)));
              return Array.from({ length: n }).map((_, i) => {
                const t = i / (n - 1);
                const v = y0 + t * (y1 - y0);
                const y = yScale(v);
                return (
                  <line
                    key={`gy-${i}`}
                    x1={PLOT_X}
                    x2={PLOT_RIGHT}
                    y1={y}
                    y2={y}
                    className="stroke-slate-100"
                  />
                );
              });
            })()}

            {/* grid X */}
            {(() => {
              const n = Math.min(6, Math.max(2, Math.floor(PLOT_W / 140)));
              const [x0, x1] = xDomain;
              return Array.from({ length: n }).map((_, i) => {
                const t = i / (n - 1);
                const ts = x0 + t * (x1 - x0);
                const x = xScale(ts);
                return (
                  <line
                    key={`gx-${i}`}
                    x1={x}
                    x2={x}
                    y1={PLOT_Y}
                    y2={PLOT_BOTTOM}
                    className="stroke-slate-100"
                  />
                );
              });
            })()}

            {/* axes */}
            <line
              x1={PLOT_X}
              x2={PLOT_RIGHT}
              y1={PLOT_BOTTOM}
              y2={PLOT_BOTTOM}
              className="stroke-slate-300"
            />
            <line
              x1={PLOT_X}
              x2={PLOT_X}
              y1={PLOT_Y}
              y2={PLOT_BOTTOM}
              className="stroke-slate-300"
            />

            {/* y labels */}
            {(() => {
              const [y0, y1] = yDomain;
              const n = Math.min(6, Math.max(2, Math.floor(PLOT_H / 60)));
              return Array.from({ length: n }).map((_, i) => {
                const t = i / (n - 1);
                const v = y0 + t * (y1 - y0);
                const y = yScale(v);
                return (
                  <text
                    key={`yl-${i}`}
                    x={PLOT_X - 8}
                    y={y}
                    textAnchor="end"
                    dominantBaseline="middle"
                    className="fill-slate-500 [font-size:clamp(10px,2.5vw,12px)]"
                  >
                    {Math.round(v)}
                  </text>
                );
              });
            })()}

            {/* x labels */}
            {(() => {
              const n = Math.min(6, Math.max(2, Math.floor(PLOT_W / 140)));
              const [x0, x1] = xDomain;
              return Array.from({ length: n }).map((_, i) => {
                const t = i / (n - 1);
                const ts = x0 + t * (x1 - x0);
                const x = xScale(ts);
                return (
                  <text
                    key={`xl-${i}`}
                    x={x}
                    y={PLOT_BOTTOM + 12}
                    textAnchor="middle"
                    dominantBaseline="hanging"
                    className="fill-slate-500 [font-size:clamp(10px,2.5vw,10px)]"
                  >
                    {new Date(ts).toLocaleDateString()}
                  </text>
                );
              });
            })()}

            {/* NP path */}
            {npPath && (
              <path
                d={npPath}
                className="stroke-blue-500 fill-none"
                strokeWidth={2}
              />
            )}

            {/* PW path */}
            {pwPath && (
              <path
                d={pwPath}
                className="stroke-green-500 fill-none"
                strokeWidth={2}
              />
            )}

            {/* Points */}
            {seriesNP.map((d) => (
              <circle
                key={`np-${d.id}`}
                cx={xScale(d.timestamp)}
                cy={yScale(d.np as number)}
                r={2}
                className="fill-blue-500"
              />
            ))}
            {seriesPW.map((d) => (
              <circle
                key={`pw-${d.id}`}
                cx={xScale(d.timestamp)}
                cy={yScale(d.pw as number)}
                r={2}
                className="fill-green-500"
              />
            ))}

            {/* Highlight current session */}
            {downsampled.some((d) => d.id === sessionId) &&
              (() => {
                const d = downsampled.find((x) => x.id === sessionId)!;
                const yVal =
                  typeof d.pw === "number"
                    ? d.pw
                    : typeof d.np === "number"
                    ? d.np
                    : yDomain[0];
                return (
                  <circle
                    cx={xScale(d.timestamp)}
                    cy={yScale(yVal as number)}
                    r={4}
                    className="fill-amber-500"
                  />
                );
              })()}

            {/* Hover crosshair */}
            {hover && (
              <>
                <line
                  x1={hover.x}
                  x2={hover.x}
                  y1={PLOT_Y}
                  y2={PLOT_BOTTOM}
                  className="stroke-slate-200"
                />
                <line
                  x1={PLOT_X}
                  x2={PLOT_RIGHT}
                  y1={hover.y}
                  y2={hover.y}
                  className="stroke-slate-200"
                />
              </>
            )}

            {/* Tooltip */}
            {hoverPoint && (
              <g>
                <rect
                  x={Math.min(
                    PLOT_RIGHT - 180,
                    Math.max(PLOT_X, xScale(hoverPoint.timestamp) + 8)
                  )}
                  y={PLOT_Y + 8}
                  width={170}
                  height={74}
                  rx={8}
                  className="fill-white stroke-slate-200"
                />
                <text
                  x={Math.min(
                    PLOT_RIGHT - 170,
                    Math.max(PLOT_X + 10, xScale(hoverPoint.timestamp) + 18)
                  )}
                  y={PLOT_Y + 24}
                  className="fill-slate-700 text-xs"
                >
                  {formatDate(hoverPoint.timestamp)}
                </text>
                <text
                  x={Math.min(
                    PLOT_RIGHT - 170,
                    Math.max(PLOT_X + 10, xScale(hoverPoint.timestamp) + 18)
                  )}
                  y={PLOT_Y + 40}
                  className="fill-blue-600 text-xs"
                >
                  NP:{" "}
                  {typeof hoverPoint.np === "number"
                    ? `${niceNum(hoverPoint.np)} W`
                    : "—"}
                </text>
                <text
                  x={Math.min(
                    PLOT_RIGHT - 170,
                    Math.max(PLOT_X + 10, xScale(hoverPoint.timestamp) + 18)
                  )}
                  y={PLOT_Y + 56}
                  className="fill-green-600 text-xs"
                >
                  PW:{" "}
                  {typeof hoverPoint.pw === "number"
                    ? `${niceNum(hoverPoint.pw)} W`
                    : "—"}
                </text>
                <text
                  x={Math.min(
                    PLOT_RIGHT - 170,
                    Math.max(PLOT_X + 10, xScale(hoverPoint.timestamp) + 18)
                  )}
                  y={PLOT_Y + 72}
                  className="fill-slate-500 text-[10px]"
                >
                  Kilde: {String(hoverPoint.source ?? (isMock ? "Mock" : "API"))} •
                  Kalibrert: {hoverPoint.calibrated ? "Ja" : "Nei"}
                </text>
              </g>
            )}
          </>
        ) : (
          // Placeholder inne i SVG så testen alltid finner role="img"
          <text
            x={PLOT_X + PLOT_W / 2}
            y={PLOT_Y + PLOT_H / 2}
            textAnchor="middle"
            dominantBaseline="middle"
            className="fill-slate-500 text-sm"
          >
            {placeholderText}
          </text>
        )}

        {/* Legend vises bare når det er plot */}
        {showPlot && (
          <g aria-label="legend">
            <circle
              cx={PLOT_X + 8}
              cy={PLOT_Y + 8}
              r={4}
              className="fill-blue-500"
            />
            <text
              x={PLOT_X + 18}
              y={PLOT_Y + 8}
              dominantBaseline="middle"
              className="fill-slate-700 text-xs"
            >
              NP
            </text>
            <circle
              cx={PLOT_X + 52}
              cy={PLOT_Y + 8}
              r={4}
              className="fill-green-500"
            />
            <text
              x={PLOT_X + 62}
              y={PLOT_Y + 8}
              dominantBaseline="middle"
              className="fill-slate-700 text-xs"
            >
              PW
            </text>
            {!haveAnyPower && (
              <text
                x={PLOT_X + 100}
                y={PLOT_Y + 8}
                dominantBaseline="middle"
                className="fill-slate-500 text-xs"
              >
                HR-only
              </text>
            )}
          </g>
        )}
      </svg>
    </div>
  );
}