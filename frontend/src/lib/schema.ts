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
  .superRefine((val, ctx) => {
    if (typeof val.avg_hr === "number" && !Number.isFinite(val.avg_hr)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["avg_hr"],
        message: "avg_hr må være et endelig tall.",
      });
    }
  })
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
