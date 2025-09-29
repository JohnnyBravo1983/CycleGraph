import { z } from 'zod'
import type { SessionReport } from '../types/session'

// Semver: basic X.Y.Z (minikrav per Sprint 8)
const SEMVER_RE = /^\d+\.\d+\.\d+$/

const NumOrNumListSchema = z.union([z.number(), z.array(z.number())]).optional().nullable()

export const SessionZodSchema = z.object({
  schema_version: z.string().regex(SEMVER_RE, 'schema_version must be semver X.Y.Z'),
  avg_hr: z.number().nullable().optional(),
  calibrated: z.boolean(),
  status: z.string(),
  watts: z.array(z.number()).nullable().optional(),
  wind_rel: NumOrNumListSchema,
  v_rel: NumOrNumListSchema,
}).passthrough()

export function parseSession(input: unknown): SessionReport {
  const parsed = SessionZodSchema.parse(input)
  // Zod returnerer en kompatibel struktur; vi bruker TS-typen vår for resten av appen
  return parsed as SessionReport
}