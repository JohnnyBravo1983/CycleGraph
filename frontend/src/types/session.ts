// Type-definisjon for SessionReport – tåler HR-only (watts kan mangle/null)
export type SessionReport = {
schema_version: string; // SemVer
avg_hr: number | null; // gjennomsnittspuls
calibrated: boolean; // om kalibrering var OK
status: string; // f.eks. "ok", "hr_only_demo", "error"


// valgfritt
watts?: number[] | null; // kan mangle eller være null ved HR-only
wind_rel?: number[] | number | null; // kan være tall eller liste
v_rel?: number[] | number | null; // kan være tall eller liste
};