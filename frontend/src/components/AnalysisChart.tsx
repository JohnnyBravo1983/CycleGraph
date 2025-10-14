// frontend/src/components/AnalysisChart.tsx
import React, { useMemo, useRef, useState, useCallback } from "react";

type CIShape = { lower?: number[]; upper?: number[] };

type Series = {
  t: number[];
  watts?: number[];
  hr?: number[];
  precision_watt_ci?: CIShape;
  ci?: CIShape;
  pw_ci?: CIShape;
};

export interface AnalysisChartProps extends React.HTMLAttributes<HTMLDivElement> {
  series: Series;
  showPower?: boolean;
  showHR?: boolean;
  showPWCI?: boolean;
  source?: "API" | "Mock" | string;
  calibrated?: boolean;
  testId?: string;
  height?: number;
}

const W = 800;
const DEFAULT_H = 320;

const PLOT_X = 44;
const PLOT_Y = 16;
const PLOT_W = 740;
const PLOT_H = 276;
const PLOT_BOTTOM = PLOT_Y + PLOT_H;

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}

function mkScaleY(min: number, max: number) {
  const span = max - min || 1;
  return (val: number) => PLOT_BOTTOM - ((val - min) / span) * PLOT_H;
}

function toPolylinePoints(xs: number[], ys: number[]): string {
  const n = Math.min(xs.length, ys.length);
  let out = "";
  for (let i = 0; i < n; i++) out += (i ? " " : "") + `${xs[i]},${ys[i]}`;
  return out;
}

function toCIBandPath(xs: number[], upperY: number[], lowerY: number[]): string {
  const n = Math.min(xs.length, upperY.length, lowerY.length);
  if (n <= 0) return "";
  if (n === 1) return `M ${xs[0]},${upperY[0]} L ${xs[0]},${lowerY[0]} Z`;
  const parts: string[] = [];
  parts.push(`M ${xs[0]},${upperY[0]}`);
  for (let i = 1; i < n; i++) parts.push(`L ${xs[i]},${upperY[i]}`);
  for (let i = n - 1; i >= 0; i--) parts.push(`L ${xs[i]},${lowerY[i]}`);
  parts.push("Z");
  return parts.join(" ");
}

type TooltipState = {
  visible: boolean;
  x: number;
  y: number;
  timeLabel: string;
  power?: number;
  hr?: number;
};

function getDataTestIdFromProps(props: unknown): string | undefined {
  if (props && typeof props === "object" && "data-testid" in props) {
    const val = (props as { ["data-testid"]?: unknown })["data-testid"];
    return typeof val === "string" ? val : undefined;
  }
  return undefined;
}

function getCI(series: Series | undefined | null): { lower: number[]; upper: number[] } {
  const s = (series ?? {}) as Partial<Series>;
  const candidates: CIShape[] = [];
  const keys = ["precision_watt_ci", "ci", "pw_ci"] as const;

  for (const k of keys) {
    const cand = s[k];
    if (!cand) continue;
    const hasSome =
      (Array.isArray(cand.lower) && cand.lower.length > 0) ||
      (Array.isArray(cand.upper) && cand.upper.length > 0);
    if (hasSome) candidates.push(cand);
  }

  if (candidates.length > 0) {
    const c = candidates[0];
    return { lower: c.lower ?? [], upper: c.upper ?? [] };
  }
  return { lower: [], upper: [] };
}

export default function AnalysisChart(props: AnalysisChartProps) {
  const {
    series,
    showPower = true,
    showHR = true,
    showPWCI = true,
    source = "API",
    calibrated: calibratedProp,
    className,
    style,
    testId,
    height = DEFAULT_H,
    ...restDivProps
  } = props;

  const t = useMemo(() => series?.t ?? [], [series]);
  const watts = useMemo(() => series?.watts ?? [], [series]);
  const hr = useMemo(() => series?.hr ?? [], [series]);

  const { lower, upper } = useMemo(() => getCI(series), [series]);

  const nT = t.length;
  const nW = watts.length;
  const nH = hr.length;
  const nCI = Math.min(lower.length, upper.length);
  const nBase = Math.max(nT, nW, nH, nCI);

  const [viewStart, setViewStart] = useState(0);
  const [viewEnd, setViewEnd] = useState(Math.max(0, nBase - 1));

  React.useEffect(() => {
    setViewStart(0);
    setViewEnd(Math.max(0, nBase - 1));
  }, [nBase]);

  const idxStart = Math.max(0, Math.min(viewStart, Math.max(0, nBase - 1)));
  const idxEnd = Math.max(idxStart, Math.min(viewEnd, Math.max(0, nBase - 1)));

  const sx_idx = useMemo(() => {
    const denom = Math.max(1, idxEnd - idxStart);
    return (i: number) => PLOT_X + ((i - idxStart) / denom) * PLOT_W;
  }, [idxStart, idxEnd]);

  const [yPowMin, yPowMax] = useMemo(() => {
    if (!showPower || nW === 0) return [100, 300];
    let mn = Infinity;
    let mx = -Infinity;
    const s = Math.max(idxStart, 0);
       const e = Math.min(idxEnd, nW - 1);
    for (let i = s; i <= e; i++) {
      const v = watts[i];
      if (Number.isFinite(v)) {
        if (v < mn) mn = v;
        if (v > mx) mx = v;
      }
    }
    if (!Number.isFinite(mn) || !Number.isFinite(mx) || mn === mx) return [0, 400];
    return [mn, mx];
  }, [showPower, nW, idxStart, idxEnd, watts]);

  const [yHrMin, yHrMax] = useMemo(() => {
    if (!showHR || nH === 0) return [100, 200];
    let mn = Infinity;
    let mx = -Infinity;
    const s = Math.max(idxStart, 0);
    const e = Math.min(idxEnd, nH - 1);
    for (let i = s; i <= e; i++) {
      const v = hr[i];
      if (Number.isFinite(v)) {
        if (v < mn) mn = v;
        if (v > mx) mx = v;
      }
    }
    if (!Number.isFinite(mn) || !Number.isFinite(mx) || mn === mx) return [100, 190];
    return [mn, mx];
  }, [showHR, nH, idxStart, idxEnd, hr]);

  const sy_pow = useMemo(() => mkScaleY(yPowMin, yPowMax), [yPowMin, yPowMax]);
  const sy_hr = useMemo(() => mkScaleY(yHrMin, yHrMax), [yHrMin, yHrMax]);

  const powerPoints = useMemo(() => {
    if (!showPower || nW === 0) return "";
    const xs: number[] = [];
    const ys: number[] = [];
    const s = Math.max(idxStart, 0);
    const e = Math.min(idxEnd, nW - 1);
    for (let i = s; i <= e; i++) {
      xs.push(sx_idx(i));
      ys.push(sy_pow(watts[i]));
    }
    return toPolylinePoints(xs, ys);
  }, [showPower, nW, idxStart, idxEnd, sx_idx, sy_pow, watts]);

  const hrPoints = useMemo(() => {
    if (!showHR || nH === 0) return "";
    const xs: number[] = [];
    const ys: number[] = [];
    const s = Math.max(idxStart, 0);
    const e = Math.min(idxEnd, nH - 1);
    for (let i = s; i <= e; i++) {
      xs.push(sx_idx(i));
      ys.push(sy_hr(hr[i]));
    }
    return toPolylinePoints(xs, ys);
  }, [showHR, nH, idxStart, idxEnd, sx_idx, sy_hr, hr]);

  const hasCIData = nCI > 0;
  const calibratedForTooltip = calibratedProp === false ? false : true;

  const shouldShowCIBand = useMemo(() => {
    if (!showPWCI) return false;
    return hasCIData;
  }, [showPWCI, hasCIData]);

  const hasCIKey = useMemo(() => {
    const s = (series ?? {}) as Partial<Series>;
    return Boolean(s?.precision_watt_ci || s?.ci || s?.pw_ci);
  }, [series]);

  const ciBandPath = useMemo(() => {
    if (!shouldShowCIBand) return "";

    const xs: number[] = [];
    const upY: number[] = [];
    const loY: number[] = [];

    const s = Math.max(idxStart, 0);
    const e = Math.min(idxEnd, Math.min(lower.length - 1, upper.length - 1));

    for (let i = s; i <= e; i++) {
      const x = sx_idx(i);
      const uRaw = upper[i];
      const lRaw = lower[i];
      const uVal = Number.isFinite(uRaw) ? (uRaw as number) : yPowMax;
      const lVal = Number.isFinite(lRaw) ? (lRaw as number) : yPowMin;

      xs.push(x);
      upY.push(sy_pow(uVal));
      loY.push(sy_pow(lVal));
    }

    if (xs.length === 0 && lower.length > 0 && upper.length > 0) {
      const i = 0;
      xs.push(sx_idx(idxStart));
      const uVal = Number.isFinite(upper[i]) ? (upper[i] as number) : yPowMax;
      const lVal = Number.isFinite(lower[i]) ? (lower[i] as number) : yPowMin;
      upY.push(sy_pow(uVal));
      loY.push(sy_pow(lVal));
    }

    if (xs.length === 0 && nCI > 0) {
      const n = Math.min(nCI, 16);
      for (let i = 0; i < n; i++) {
        const frac = n === 1 ? 0 : i / (n - 1);
        const x = PLOT_X + frac * PLOT_W;
        const idx = Math.round(frac * (nCI - 1));
        const uRaw = upper[idx];
        const lRaw = lower[idx];
        const uVal = Number.isFinite(uRaw) ? (uRaw as number) : yPowMax;
        const lVal = Number.isFinite(lRaw) ? (lRaw as number) : yPowMin;
        xs.push(x);
        upY.push(sy_pow(uVal));
        loY.push(sy_pow(lVal));
      }
    }

    return toCIBandPath(xs, upY, loY);
  }, [shouldShowCIBand, idxStart, idxEnd, lower, upper, sx_idx, sy_pow, yPowMax, yPowMin, nCI]);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const [tooltip, setTooltip] = useState<TooltipState>({
    visible: false,
    x: 0,
    y: 0,
    timeLabel: "",
  });
  const sourceLabel = String(source ?? "");

  const formatTime = useCallback(
    (idx: number) => {
      const raw = t?.[idx] ?? idx;
      if (Number.isFinite(raw)) {
        const sec = Math.max(0, Math.floor(Number(raw)));
        const h = Math.floor(sec / 3600);
        const m = Math.floor((sec % 3600) / 60);
        const s = sec % 60;
        const pad = (n: number) => (n < 10 ? `0${n}` : `${n}`);
        return `${pad(h)}:${pad(m)}:${pad(s)}`;
      }
      return `${idx}`;
    },
    [t]
  );

  // Konverter global client-koordinat til lokale SVG-koordinater (med fallback for jsdom)
  const clientToLocal = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current;
    const div = containerRef.current;
    const rect = (svg ?? div)?.getBoundingClientRect?.();
    if (!rect || rect.width === 0 || rect.height === 0) {
      // jsdom fallback: ingen layout -> returner plottets start
      return { x: PLOT_X, y: PLOT_Y, rectOk: false };
    }
    return {
      x: clientX - rect.left,
      y: clientY - rect.top,
      rectOk: true,
    };
  }, []);

  // Mappe x-posisjon i plottet til nærmeste indeks
  const pickIndexFromClientX = useCallback((clientX: number) => {
    const { x, rectOk } = clientToLocal(clientX, 0);
    if (!rectOk) {
      // jsdom fallback
      return clamp(Math.round((idxStart + idxEnd) / 2), 0, Math.max(0, nBase - 1));
    }
    const px = clamp(x, PLOT_X, PLOT_X + PLOT_W);
    const frac = (px - PLOT_X) / Math.max(1, PLOT_W);
    const idx = Math.round(idxStart + frac * (idxEnd - idxStart));
    return clamp(idx, 0, Math.max(0, nBase - 1));
  }, [clientToLocal, idxStart, idxEnd, nBase]);

  const showTooltipAt = useCallback(
    (clientX: number, clientY: number) => {
      const idx = pickIndexFromClientX(clientX);
      const { x, y } = clientToLocal(clientX, clientY);
      // Plasser tooltip i lokal coords, klampet til plottområde
      const tx = clamp(x, PLOT_X, PLOT_X + PLOT_W);
      const ty = clamp(y, PLOT_Y, PLOT_Y + PLOT_H);
      setTooltip({
        visible: true,
        x: tx,
        y: ty,
        timeLabel: formatTime(idx),
        power: watts[idx],
        hr: hr[idx],
      });
    },
    [pickIndexFromClientX, clientToLocal, formatTime, watts, hr]
  );

  // Handlers – bruk Element slik at både <svg> og hit-<rect> støttes
  const handlePointerEnter = useCallback((ev: React.PointerEvent<Element>) => {
    showTooltipAt(ev.clientX, ev.clientY);
  }, [showTooltipAt]);

  const handlePointerMove = useCallback((ev: React.PointerEvent<Element>) => {
    showTooltipAt(ev.clientX, ev.clientY);
  }, [showTooltipAt]);

  const handlePointerLeave = useCallback(() => {
    setTooltip((prev) => ({ ...prev, visible: false }));
  }, []);

  const handleWheel = useCallback(() => {
    /* noop for tester */
  }, []);

  const handleMouseEnter = useCallback((ev: React.MouseEvent<Element>) => {
    showTooltipAt(ev.clientX, ev.clientY);
  }, [showTooltipAt]);

  const handleMouseMove = useCallback((ev: React.MouseEvent<Element>) => {
    showTooltipAt(ev.clientX, ev.clientY);
  }, [showTooltipAt]);

  const handleMouseLeave = useCallback(() => {
    setTooltip((prev) => ({ ...prev, visible: false }));
  }, []);

  const shouldRenderFallback =
    (!powerPoints || powerPoints.length === 0) && (!hrPoints || hrPoints.length === 0);

  const fallbackPoints = `${PLOT_X + PLOT_W / 2},${PLOT_Y + PLOT_H / 2}`;

  const dataTestId = testId ?? getDataTestIdFromProps(restDivProps) ?? "chart";

  return (
    <div
      ref={containerRef}
      className={`w-full relative select-none ${className ?? ""}`}
      style={style}
      {...restDivProps}
      data-testid={dataTestId}
    >
      <svg
        ref={svgRef}
        role="img"
        aria-label="Analysis time series"
        className="bg-white"
        width="100%"
        height={height}
        viewBox={`0 0 ${W} ${DEFAULT_H}`}
        preserveAspectRatio="none"
        style={{ cursor: "crosshair" }}
        onWheel={handleWheel}
        /* også på svg for testene */
        onPointerEnter={handlePointerEnter}
        onPointerMove={handlePointerMove}
        onPointerLeave={handlePointerLeave}
        onMouseEnter={handleMouseEnter}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        <rect className="fill-white stroke-slate-200" x={PLOT_X} y={PLOT_Y} width={PLOT_W} height={PLOT_H} />
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
          <line
            key={`h-${i}`}
            className="stroke-slate-100"
            x1={PLOT_X}
            x2={PLOT_X + PLOT_W}
            y1={PLOT_Y + (i * PLOT_H) / 6}
            y2={PLOT_Y + (i * PLOT_H) / 6}
          />
        ))}
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
          <line
            key={`v-${i}`}
            className="stroke-slate-100"
            x1={PLOT_X + (i * PLOT_W) / 6}
            x2={PLOT_X + (i * PLOT_W) / 6}
            y1={PLOT_Y}
            y2={PLOT_Y + PLOT_H}
          />
        ))}

        {/* CI-bånd: la hendelser slippe gjennom */}
        {showPWCI && hasCIKey && (
          <path
            className="fill-slate-200 opacity-60"
            d={ciBandPath}
            data-testid="ci-band"
            pointerEvents="none"
          />
        )}

        {powerPoints && powerPoints.length > 0 && (
          <polyline className="fill-none stroke-blue-500" points={powerPoints} />
        )}

        {hrPoints && hrPoints.length > 0 && (
          <polyline className="fill-none stroke-red-500" points={hrPoints} />
        )}

        {shouldRenderFallback && <polyline className="fill-none stroke-slate-300" points={fallbackPoints} />}

        {/* Interaksjonslag over hele plottområdet – fanger hover uansett */}
        <rect
          x={PLOT_X}
          y={PLOT_Y}
          width={PLOT_W}
          height={PLOT_H}
          fill="transparent"
          pointerEvents="all"
          data-testid="plot-hit-rect"
          onPointerEnter={handlePointerEnter}
          onPointerMove={handlePointerMove}
          onPointerLeave={handlePointerLeave}
          onMouseEnter={handleMouseEnter}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        />
      </svg>

      {tooltip.visible && (
        <div
          className="absolute pointer-events-none shadow rounded bg-white/90 text-xs px-2 py-1"
          data-testid="tooltip"
          style={{ left: tooltip.x, top: tooltip.y }}
          role="tooltip"
        >
          <div>{tooltip.timeLabel || "00:00:00"}</div>
          {tooltip.power != null && Number.isFinite(tooltip.power) && (
            <div>Power: {Math.round(tooltip.power)} W</div>
          )}
          {tooltip.hr != null && Number.isFinite(tooltip.hr) && <div>HR: {Math.round(tooltip.hr)} bpm</div>}
          <div data-testid="tooltip-meta">
            {`Kilde: ${String(sourceLabel)} – Kalibrert: ${calibratedForTooltip ? "Ja" : "Nei"}`}
          </div>
        </div>
      )}
    </div>
  );
}
