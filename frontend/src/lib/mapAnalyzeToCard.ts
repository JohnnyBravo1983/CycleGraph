// frontend/src/lib/mapAnalyzeToCard.ts
import type { AnalyzeResponse } from "./schema";

// Returntype matches SessionWithCalib (SessionCard.tsx)
export function mapAnalyzeToCard(
  ar: AnalyzeResponse | null | undefined
) {
  if (!ar) return null;

  const metrics = ar.metrics;
  const prof = metrics.profile_used;

  // PW
  const pw = metrics.precision_watt ?? null;

  // CI
  const ci =
    metrics.estimated_error_pct_range &&
    metrics.estimated_error_pct_range.length === 2
      ? ([
          metrics.estimated_error_pct_range[0],
          metrics.estimated_error_pct_range[1],
        ] as [number, number])
      : null;

  return {
    // --- Core ---
    schema_version: "1.0.0",
    calibrated: metrics.calibrated ?? false,
    status: "ok",

    // --- Raw watts ---
    watts: ar.samples?.map((s) => s[0]) ?? null,

    // --- PrecisionWatt ---
    precision_watt: pw,
    precision_watt_value: pw,
    precision_watt_ci: ci,
    precision_quality_hint: metrics.calibration_status ?? null,
    estimated_error_pct_range: ci,

    // --- Aero / rolling ---
    CdA: prof.cda ?? null,
    crr_used: prof.crr ?? null,

    // --- Bike / rider ---
    rider_weight: prof.weight_kg ?? null,
    bike_weight: null, // backend has no bike_weight_kg
    tire_width: prof.tire_width_mm ?? null,
    bike_type: prof.bike_type ?? null,

    // sources must NEVER be null (SessionWithCalib requirement)
    sources: ["analysis"],

    // --- Legacy fields not in analyzer ---
    reason: null,
    np: null,
    if_: null,
    vi: null,
    pa_hr: null,
    w_per_beat: null,
    cgs: null,

    // frontend heuristic
    mode: "outdoor",

    has_gps: metrics.weather_used ?? false,
  };
}
