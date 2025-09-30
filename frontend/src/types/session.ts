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
};