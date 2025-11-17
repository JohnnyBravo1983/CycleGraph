// frontend/src/lib/schema.ts
import { z } from "zod";
import type { SessionReport } from "../types/session";

/**
 * Semver (Sprint 8 minimum): X.Y.Z
 * Eksempler: 1.0.0, 0.9.2 — (ingen prerelease/build-krav i denne sprinten)
 */
export const SEMVER_RE = /^\d+\.\d+\.\d+$/;

/** Tall eller liste av tall — kan være optional/null (HR-only / tolerant schema) */
export const NumOrNumListSchema = z
  .union([z.number(), z.array(z.number())])
  .optional()
  .nullable();

/**
 * Zod-schema for session-objektet.
 * Beholder din eksisterende kontrakt:
 * - schema_version: enkel semver X.Y.Z
 * - avg_hr: number | null | undefined
 * - calibrated: boolean
 * - status: string
 * - watts: number[] | null | undefined  (NB: liste når tilstede)
 * - wind_rel/v_rel: number | number[] | null | undefined
 * - .passthrough() for å akseptere flere felt uten å feile
 */
export const SessionZodSchema = z
  .object({
    schema_version: z
      .string()
      .regex(SEMVER_RE, "schema_version must be semver X.Y.Z"),
    avg_hr: z.number().nullable().optional(),
    calibrated: z.boolean(),
    status: z.string(),
    watts: z.array(z.number()).nullable().optional(), // beholdt som hos deg
    wind_rel: NumOrNumListSchema,
    v_rel: NumOrNumListSchema,
  })
  // Ekstra defensivitet: hvis avg_hr finnes, må den være et endelig tall (ikke NaN/Infinity)
    .superRefine(
    (val: { avg_hr?: number | null }, ctx: z.RefinementCtx) => {
      if (typeof val.avg_hr === "number" && !Number.isFinite(val.avg_hr)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["avg_hr"],
          message: "avg_hr må være et endelig tall.",
        });
      }
    }
  )
  .passthrough();

/** Kaster ved feil; returnerer TS-typen din for videre bruk */
export function parseSession(input: unknown): SessionReport {
  const parsed = SessionZodSchema.parse(input);
  return parsed as SessionReport;
}

/** Lettvekts helper for eksplisitt semver-sjekk når du vil feile tidlig */
export function ensureSemver(v: string): void {
  if (!SEMVER_RE.test(v)) {
    throw new Error("Ugyldig schema_version (må være semver X.Y.Z)");
  }
}

/**
 * Trygg parser som ikke kaster — nyttig i adapteret for kontrollert feil.
 * Beholder nøyaktig samme returtype som du har, men forbedrer feilmeldingen.
 */
export function safeParseSession(
  input: unknown
): { ok: true; data: SessionReport } | { ok: false; error: string } {
  const res = SessionZodSchema.safeParse(input);
  if (res.success) {
    return { ok: true, data: res.data as SessionReport };
  }
  // Kompakt, men informativ feilmelding (første hovedfeil)
  const first =
    res.error.issues?.[0]?.message ||
    res.error.message ||
    "Ugyldig session-schema.";
  return { ok: false, error: first };
}

/* ------------------------------------------------------------------
 * Sprint 15 – Analyze / Profile / Trend kontrakt (frontend-typer)
 * Basert på Layer 1 MASTER SPEC + backend stability-rapport.
 * ------------------------------------------------------------------ */

export interface AnalyzeProfileUsed {
  cda: number;
  crr: number;
  crank_efficiency: number;
  weight_kg: number;
  bike_type: string;
  tire_width_mm: number;
  tire_quality: string;
  profile_version: number;
}

export interface AnalyzeMetrics {
  // Alltid tilstede – men verdier kan være null (backend-kontrakt)
  precision_watt: number | null;
  drag_watt: number | null;
  rolling_watt: number | null;
  total_watt: number | null;

  calibration_mae: number | null;
  calibrated: boolean | null;
  calibration_status: string | null;

  weather_used: boolean | null;
  weather_meta: Record<string, unknown> | null;
  weather_fp: string | null;

  // Backend sender også profile_used inn her for tracing
  profile_used: AnalyzeProfileUsed;

  // Sprint 15-spesifikke felter
  estimated_error_pct_range: [number, number] | null;
  precision_quality_hint: string | null;
  profile_completeness: number | null;
}

export type SampleTuple = [number, number, number];

export interface AnalyzeResponse {
  source: string;
  weather_applied: boolean;
  weather_source: string;
  profile_version: number;

  metrics: AnalyzeMetrics;
  profile_used: AnalyzeProfileUsed;

  samples: SampleTuple[];

  publish?: {
    time?: string | null;
    status?: string | null;
    strava_url?: string | null;
  };
}

/**
 * Profil-kontrakt for GET/PUT /profile.
 * Frontend skal:
 *  - Vise editable: rider_weight_kg, bike_weight_kg, bike_type, tire_width_mm,
 *    tire_quality, bike_name, cda
 *  - Vise ikke-editable: crank_efficiency (96%), profile_version
 *  - Ha toggle: publish_to_strava
 */
export interface Profile {
  rider_weight_kg: number;
  bike_weight_kg: number;
  bike_type: string;
  tire_width_mm: number;
  tire_quality: string;
  bike_name?: string | null;
  cda: number;

  crank_efficiency: number; // låst til 96% nå
  profile_version: number;

  publish_to_strava?: boolean;
}

/**
 * CSV-basert trendkontrakt.
 * - summary.csv: kolonner date,session_id,avg_watt,avg_hr,w_per_beat,cda_used,crr_used
 * - pivot/<metric>.csv: kolonner weather_source,mean,std,count
 */
export type CsvRows = string[][];

export interface TrendSummary {
  rows: CsvRows;
}

export interface TrendPivot {
  rows: CsvRows;
}
