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
 * Nå *ekstra* tolerant:
 * - alle felt er optional
 * - calibrated godtar boolean | number | string | null | undefined
 * - .passthrough() lar resten flyte
 */
export const SessionZodSchema = z
  .object({
    schema_version: z
      .string()
      .regex(SEMVER_RE, "schema_version must be semver X.Y.Z")
      .optional(),

    avg_hr: z.number().nullable().optional(),

    // 👇 ekstra tolerant, siden backend kan sende f.eks. 0/1 eller "true"/"false" eller mangle helt
    calibrated: z
      .union([z.boolean(), z.number(), z.string()])
      .nullable()
      .optional(),

    status: z.string().optional(),

    watts: z.array(z.number()).nullable().optional(),

    wind_rel: NumOrNumListSchema.optional(),
    v_rel: NumOrNumListSchema.optional(),
  })
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
export function ensureSemver(v: string | undefined): void {
  if (!v || !SEMVER_RE.test(v)) {
    throw new Error("Ugyldig schema_version (må være semver X.Y.Z)");
  }
}

/**
 * Trygg parser som ikke kaster — nyttig i adapteret for kontrollert feil.
 */
export function safeParseSession(
  input: unknown
): { ok: true; data: SessionReport } | { ok: false; error: string } {
  const res = SessionZodSchema.safeParse(input);
  if (res.success) {
    return { ok: true, data: res.data as SessionReport };
  }
  const first =
    res.error.issues?.[0]?.message ||
    res.error.message ||
    "Ugyldig session-schema.";
  return { ok: false, error: first };
}
