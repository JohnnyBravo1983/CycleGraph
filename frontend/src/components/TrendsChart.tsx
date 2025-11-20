import React, { useEffect, useMemo, useState } from "react";
import { fetchCsv } from "../lib/api";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
} from "recharts";

const DEBUG_LOG = import.meta.env.MODE === "development";
const SHOW_DEBUG_PANEL = false; // sett til true når du vil se JSON-dumpen igjen

export interface TrendsChartProps {
  sessionId: string;
  isMock: boolean;
  series?: { t: number[]; watts?: number[]; hr?: number[] };
  hrOnly?: boolean;
  calibrated?: boolean | null;
  source?: "API" | "Mock" | string;
}

function getRuntimeMode(): string {
  let viteMode: string | undefined;
  try {
    viteMode =
      (typeof import.meta !== "undefined" &&
        (import.meta as unknown as { env?: Record<string, string | undefined> })
          .env?.MODE) ||
      undefined;
  } catch {
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

type DebugTrendPoint = {
  sessionId: string;
  date: string;
  avgWatt: number | null;
  avgHr: number | null;
  mode: string | null;
};

type PivotDebugPoint = {
  metric: string;
  bin: string;
  value: number;
};

export default function TrendsChart(props: TrendsChartProps) {
  const { sessionId, isMock } = props;

  const [rechartsFallbackData, setRechartsFallbackData] = useState<
    { date: string; avgWatt: number }[]
  >([]);

  const [debugPoints, setDebugPoints] = useState<DebugTrendPoint[]>([]);
  const [pivotPoints, setPivotPoints] = useState<PivotDebugPoint[]>([]);

  const autoHrOnly = useMemo(() => {
    const hrLen = props.series?.hr?.length ?? 0;
    const wLen = props.series?.watts?.length ?? 0;
    return hrLen > 0 && wLen === 0;
  }, [props.series?.hr?.length, props.series?.watts?.length]);

  const computedHrOnly = props.hrOnly ?? autoHrOnly ?? false;

  useEffect(() => {
    let cancelled = false;

    async function load() {
      // Hvis vi bare har puls-serie → ingen watt-trender å vise
      if (computedHrOnly) {
        setDebugPoints([]);
        setPivotPoints([]);
        setRechartsFallbackData([]);
        return;
      }

      const testEnv = isTestEnv();
      const liveActive = isLiveTrendsEnv();
      const mockActive = !liveActive && (isMock || (!testEnv && isMockEnv()));

      // MOCK-mode: generer fake trend-punkter uten å kalle backend
      if (!testEnv && mockActive) {
        const now = Date.now();
        const pts: DebugTrendPoint[] = Array.from({ length: 30 }).map(
          (_, i) => {
            const date = new Date(
              now - (30 - i) * 2 * 24 * 3600 * 1000,
            )
              .toISOString()
              .split("T")[0];
            const avgWatt = 200 + i * 3;
            const avgHr = 150 + i;
            return {
              sessionId: `mock-${i}`,
              date,
              avgWatt,
              avgHr,
              mode: "cycling",
            };
          },
        );

        if (!cancelled) {
          setDebugPoints(pts);
          setPivotPoints([]);
          setRechartsFallbackData(
            pts.map((p) => ({
              date: p.date,
              avgWatt: p.avgWatt ?? 0,
            })),
          );
        }
        return;
      }

      try {
        if (DEBUG_LOG) {
          console.log("[TRENDS] henter summary + pivot fra backend (live)");
        }

        // 1) Hent summary + pivot parallelt
        const [summaryRaw, pivotRaw] = await Promise.all([
          fetchCsv("/trend/summary.csv"),
          fetchCsv("/trend/pivot/avg_watt.csv?profile_version=0").catch(
            (err) => {
              if (DEBUG_LOG) {
                console.warn(
                  "[TRENDS] klarte ikke å hente pivot CSV",
                  err,
                );
              }
              return "";
            },
          ),
        ]);

        if (cancelled) return;

        // --- SUMMARY (som før, men mer robust) ---
        const summaryNorm = summaryRaw.replace(/\r\n/g, "\n").trim();
        if (DEBUG_LOG) {
          console.log(
            "[TRENDS] raw summary length",
            summaryNorm.length,
          );
        }

        const summaryLines = summaryNorm
          .split("\n")
          .filter((l) => l.trim().length > 0);

        if (!summaryLines.length) {
          if (DEBUG_LOG) {
            console.log("[TRENDS] summary.csv er tom");
          }
          setDebugPoints([]);
          setRechartsFallbackData([]);
        } else {
          const [headerLine, ...dataLines] = summaryLines;
          if (DEBUG_LOG) {
            console.log("[TRENDS] summary header =", headerLine);
            console.log(
              "[TRENDS] summary data rows =",
              dataLines.length,
            );
            if (dataLines[0]) {
              console.log(
                "[TRENDS] first data row =",
                dataLines[0],
              );
            }
          }

          const headerCols = headerLine.split(",");
          const idxSession = headerCols.indexOf("session_id");
          const idxDate = headerCols.indexOf("date");
          const idxAvgWatt = headerCols.indexOf("avg_watt");
          const idxAvgHr = headerCols.indexOf("avg_hr");
          const idxMode = headerCols.indexOf("mode");

          const parsedSummary: DebugTrendPoint[] = dataLines
            .map((line) => line.split(","))
            .map((cols) => {
              const sessionId =
                idxSession >= 0 ? cols[idxSession] : cols[0];
              const date =
                idxDate >= 0 ? cols[idxDate] : "";
              const avgWattStr =
                idxAvgWatt >= 0 ? cols[idxAvgWatt] : "";
              const avgHrStr =
                idxAvgHr >= 0 ? cols[idxAvgHr] : "";
              const mode =
                idxMode >= 0 ? cols[idxMode] || null : null;

              const avgWatt =
                avgWattStr &&
                Number.isFinite(parseFloat(avgWattStr))
                  ? parseFloat(avgWattStr)
                  : null;
              const avgHr =
                avgHrStr &&
                Number.isFinite(parseFloat(avgHrStr))
                  ? parseFloat(avgHrStr)
                  : null;

              return { sessionId, date, avgWatt, avgHr, mode };
            })
            .filter((p) => p.date && p.avgWatt != null);

          if (DEBUG_LOG) {
            console.log(
              "[TRENDS] debugPoints count =",
              parsedSummary.length,
            );
            if (parsedSummary.length > 0) {
              console.log(
                "[TRENDS] first debugPoint =",
                parsedSummary[0],
              );
            }
          }

          setDebugPoints(parsedSummary);

          const rechartsData = parsedSummary.map((p) => ({
            date: p.date,
            avgWatt: p.avgWatt as number,
          }));
          setRechartsFallbackData(rechartsData);
        }

        // --- PIVOT (NY) ---
        const pivotTrimmed = pivotRaw.replace(/\r\n/g, "\n").trim();
        if (!pivotTrimmed) {
          if (DEBUG_LOG) {
            console.log(
              "[TRENDS] pivot CSV tom / ikke tilgjengelig",
            );
          }
          setPivotPoints([]);
          return;
        }

        const pivotLines = pivotTrimmed
          .split("\n")
          .filter((l) => l.trim().length > 0);
        if (pivotLines.length <= 1) {
          if (DEBUG_LOG) {
            console.log(
              "[TRENDS] pivot har bare header, ingen data",
            );
          }
          setPivotPoints([]);
          return;
        }

        const [pivotHeaderLine, ...pivotDataLines] = pivotLines;
        if (DEBUG_LOG) {
          console.log("[TRENDS] pivot header =", pivotHeaderLine);
        }

        const pivotHeaderCols = pivotHeaderLine.split(",");
        const idxMetric = pivotHeaderCols.indexOf("metric");
        const idxBin = pivotHeaderCols.indexOf("bin");
        const idxValue = pivotHeaderCols.indexOf("value");

        const parsedPivot: PivotDebugPoint[] = pivotDataLines
          .map((line) => line.split(","))
          .map((cols) => {
            const metric =
              idxMetric >= 0 ? cols[idxMetric] : cols[0];
            const bin =
              idxBin >= 0 ? cols[idxBin] : cols[1] ?? "";
            const valueStr =
              idxValue >= 0 ? cols[idxValue] : cols[2] ?? "";
            const value = parseFloat(valueStr);
            return { metric, bin, value };
          })
          .filter((p) => p.bin && Number.isFinite(p.value));

        if (DEBUG_LOG) {
          console.log(
            "[TRENDS] pivotPoints count =",
            parsedPivot.length,
          );
          if (parsedPivot.length > 0) {
            console.log(
              "[TRENDS] first pivotPoint =",
              parsedPivot[0],
            );
          }
        }

        setPivotPoints(parsedPivot);
      } catch (err) {
        if (DEBUG_LOG) {
          console.error(
            "[TRENDS] klarte ikke å laste trend-data",
            err,
          );
        }
        if (!cancelled) {
          setDebugPoints([]);
          setPivotPoints([]);
          setRechartsFallbackData([]);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [isMock, computedHrOnly, sessionId]);

  // Derivert datasett for pivot-graf (sortert på bin)
  const pivotChartData = useMemo(
    () =>
      pivotPoints
        .slice()
        .sort((a, b) => a.bin.localeCompare(b.bin)),
    [pivotPoints],
  );

  // --- Render ------------------------------------------------------------

  // Tom-state: ingen punkter ennå
  if (!debugPoints || debugPoints.length === 0) {
    if (DEBUG_LOG) {
      console.log(
        "[TRENDS] rendering EMPTY state (ingen debugPoints)",
      );
    }

    return (
      <section className="mt-4 rounded-xl border border-dashed border-gray-300 p-4 text-sm text-gray-600">
        <h3 className="mb-1 font-semibold text-gray-900">
          Trend – avg watt
        </h3>
        <p>
          Ingen trenddata tilgjengelig ennå. Kjør minst én analyse i
          backend (multi-ride scriptet) for å generere{" "}
          <code>summary.csv</code>.
        </p>
      </section>
    );
  }

  if (DEBUG_LOG) {
    console.log(
      "[TRENDS] rendering DEBUG chart, points=",
      debugPoints.length,
    );
  }

  return (
    <section className="mt-4 space-y-6">
      <header className="flex items-baseline justify-between">
        <h3 className="font-semibold text-gray-900">
          Trend – avg watt (live summary.csv)
        </h3>
        <span className="text-xs text-gray-500">
          {debugPoints.length} punkt
        </span>
      </header>

      {/* Hoved-trendlinje */}
      <div className="h-64 w-full flex items-center justify-center">
        <LineChart
          width={720}
          height={240}
          data={rechartsFallbackData}
          margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="avgWatt" dot={false} />
        </LineChart>
      </div>

      {/* Pivot-graf – vises kun hvis vi har pivot-data */}
      <section className="space-y-2">
        <header className="flex items-baseline justify-between">
          <h4 className="font-medium text-gray-900">
            Pivot – avg watt per bin
          </h4>
          <span className="text-xs text-gray-500">
            {pivotChartData.length} rader
          </span>
        </header>

        {pivotChartData.length === 0 ? (
          <p className="text-xs text-gray-500">
            Ingen pivot-data tilgjengelig (backend returnerer kun header
            foreløpig).
          </p>
        ) : (
          <div className="h-64 w-full flex items-center justify-center">
            <BarChart
              width={720}
              height={240}
              data={pivotChartData}
              margin={{ top: 10, right: 30, left: 0, bottom: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="bin"
                angle={-45}
                textAnchor="end"
                height={60}
              />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" />
            </BarChart>
          </div>
        )}
      </section>

      {SHOW_DEBUG_PANEL && (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-700 space-y-4">
          {/* SUMMARY-debug */}
          <div>
            <div className="font-semibold">
              Debug-data fra summary.csv
            </div>
            <div>Antall punkter: {debugPoints.length}</div>
            <div>Første 5 datapunkter:</div>
            <pre className="mt-1 max-h-48 overflow-auto rounded bg-muted p-2">
              {JSON.stringify(debugPoints.slice(0, 5), null, 2)}
            </pre>
          </div>

          {/* PIVOT-debug */}
          <div className="border-t pt-2">
            <div className="font-semibold">
              Debug-data fra pivot/avg_watt.csv
            </div>
            <div>Antall rader: {pivotPoints.length}</div>
            <div>Første 5 rader:</div>
            <pre className="mt-1 max-h-48 overflow-auto rounded bg-muted p-2">
              {JSON.stringify(pivotPoints.slice(0, 5), null, 2)}
            </pre>
          </div>
        </div>
      )}
    </section>
  );
}
