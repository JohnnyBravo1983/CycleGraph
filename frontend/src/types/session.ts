// frontend/src/types/session.ts

// ─────────────────────────────────────────────────────────────────────────────
// Type-definisjon for SessionReport – tåler HR-only (watts kan mangle/null)
// ─────────────────────────────────────────────────────────────────────────────

export type SessionMode = "indoor" | "outdoor";

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
  | "np"
  | "if_"
  | "vi"
  | "pa_hr"
  | "w_per_beat"
  | "cgs"
  | "precision_watt_value"
>;

/* ────────────────────────────────────────────────────────────────────────────
   S14: SessionMetrics (lagring/persistens) i tråd med schema/session_metrics.v1.json
   Dette er aggregerte felter per økt (ikke samme som SessionReport-streams).
   Alle nye felt er valgfrie for bakoverkompatibilitet.
──────────────────────────────────────────────────────────────────────────── */

export type PublishState = "none" | "pending" | "published" | "failed";

/** Match mot schema/session_metrics.v1.json */
export interface SessionMetrics {
  user_id: string;
  date: string; // ISO-date (YYYY-MM-DD)
  avg_watt: number;
  duration_min: number;

  // S14 – Bike Setup / fysikk
  bike_type?: string;
  bike_weight?: number; // kg
  tire_width?: number; // mm
  tire_quality?: string; // "Trening" | "Vanlig" | "Ritt" | fri tekst
  crr_used?: number;
  rider_weight?: number; // kg
  bike_name?: string;

  // S14 – Precision Watt (aggregert/lagret per økt)
  precision_watt?: number;
  precision_watt_ci?: number;

  // S14 – Publisering til Strava
  publish_state?: PublishState;
  publish_hash?: string;
  published_to_strava?: boolean;
  publish_time?: string; // ISO date-time

  // Schema-versjon (v0.7.x)
  schema_version: string;
}

/** S15: SessionInfo – lettvekts-meta om økten til bruk i lister/oversikter */
export type SessionInfo = {
  /** Backend-session id – brukes både i API og i /session/:id (kan mangle i dagens backend) */
  session_id: string;

  /** Optional Strava ride id, hvis backend speiler dette */
  ride_id?: string | null;

  /** Menneskelig lesbar label/tittel hvis tilgjengelig */
  label?: string | null;

  /** Starttidspunkt for økten (ISO-string) */
  started_at?: string | null;

  /** Om økten var indoor/outdoor hvis kjent */
  mode?: SessionMode | null;

  /** Nytt: værkilde brukt i analysen (fra /sessions/list) */
  weather_source?: string | null;

  /** Nytt: hvilken profil-versjon som ble brukt */
  profile_version?: string | null;
};