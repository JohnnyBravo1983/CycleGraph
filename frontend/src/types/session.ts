// frontend/src/types/session.ts

// ─────────────────────────────────────────────────────────────────────────────
// Type-definisjon for SessionReport – tåler HR-only (watts kan mangle/null)
// ─────────────────────────────────────────────────────────────────────────────

export type SessionMode = 'indoor' | 'outdoor';

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

  /**
   * Precision Watt (PW) – valgfri stub for S8.5
   * number[]: PW per sample (samme rekkefølge som watts/hr)
   * null: feltet finnes, men ingen data
   * undefined: feltet mangler (eldre schema)
   */
  precision_watt?: number[] | null;

  /**
   * PW konfidensintervall per sample [low, high]
   * Lengde bør matche precision_watt hvis tilstede
   */
  precision_watt_ci?: [number, number][] | null;

  /**
   * Datakilder som har påvirket beregningene (telemetri/modeller)
   * f.eks. ["powermeter","weather","profile"]
   */
  sources?: string[] | null;

  /**
   * Aerodynamisk dragkoeffisient (valgfritt i S8.5)
   */
  cda?: number | null;

  /**
   * Rullemostand (valgfritt i S8.5)
   */
  crr?: number | null;

  /**
   * Forklaringsfelt/årsaksbeskrivelse for begrenset visning eller valg
   * f.eks. "short_session" / "hr_only_demo" / "no_power_data"
   */
  reason?: string | null;

  /** ───────── S9: Nøkkelmetrikker (alle optional + null-sikret) ───────── */
  /** Normalized Power (W) */
  np?: number | null;

  /** Intensity Factor (0–2). Underscore for å unngå kollisjon med reserverte navn */
  if_?: number | null;

  /** Variability Index (typisk 1.0–2.0+) */
  vi?: number | null;

  /** Pa:Hr (lagres som ratio, f.eks. 0.035 = 3.5 %). Formatteres til % i UI. */
  pa_hr?: number | null;

  /** Watt per hjerteslag (W/slag) */
  w_per_beat?: number | null;

  /** CycleGraph Score (skala 0–100 eller flyttall) */
  cgs?: number | null;

  /** Precision Watt — aggregert verdi (W), ikke graf i S9 */
  precision_watt_value?: number | null;

  /** ───────── S9: Indoor/Outdoor + GPS (valgfritt for bakoverkomp) ───────── */
  /** Eksplisitt modus for visning av chip/badge i UI */
  mode?: SessionMode;

  /** Om økten hadde GPS-telemetri tilgjengelig (kan brukes for avledning) */
  has_gps?: boolean;
};

// Hjelpetype for å plukke ut nøkkelmetrikker i UI (SessionCard m.m.)
export type KeyMetrics = Pick<
  SessionReport,
  | 'np'
  | 'if_'
  | 'vi'
  | 'pa_hr'
  | 'w_per_beat'
  | 'cgs'
  | 'precision_watt_value'
>;