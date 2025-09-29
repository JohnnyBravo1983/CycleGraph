// frontend/src/types/session.ts

// Type-definisjon for SessionReport – tåler HR-only (watts kan mangle/null)
export type SessionReport = {
  schema_version: string; // SemVer
  avg_hr: number | null; // gjennomsnittspuls
  calibrated: boolean; // om kalibrering var OK
  status: string; // f.eks. "ok", "hr_only_demo", "error"

  // Valgfritt – støtter enkelverdi, liste eller null
  watts?: number | number[] | null;

  // Kan være tall, liste eller null
  wind_rel?: number | number[] | null;
  v_rel?: number | number[] | null;
};