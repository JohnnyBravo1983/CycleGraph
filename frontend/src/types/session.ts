// frontend/src/types/session.ts

/** En linje i sessions-lista (/api/sessions/list) */
export interface SessionListItem {
  /** Unik ID for økt på serversiden (kan være lik ride_id, men vi skiller de) */
  session_id: string;

  /** Strava- eller internt ride-id */
  ride_id: string;

  /** Menneskelig / ISO starttidspunkt */
  start_time?: string | null;

  /** Total distanse i kilometer */
  distance_km?: number | null;

  /** Gjennomsnittlig Precision Watt for økta (snitt) */
  precision_watt_avg?: number | null;

  /** F.eks. "v1-a0c54a9e-20251209" */
  profile_label?: string | null;

  /** F.eks. "open-meteo" / "open-meteo/era5" */
  weather_source?: string | null;
}

export type SessionMode = "indoor" | "outdoor";

/**
 * “Loose” objekt-type uten any (for å unngå eslint @typescript-eslint/no-explicit-any).
 * Brukes kun til å beskrive ukjente JSON-objekter.
 */
export type UnknownRecord = Record<string, unknown>;

/**
 * Minimal “metrics” shape som UI-en din leser fra.
 * Resten kan ligge som ukjente felter.
 */
export interface SessionMetrics extends UnknownRecord {
  precision_watt?: number | null;
  total_watt?: number | null;
  drag_watt?: number | null;
  rolling_watt?: number | null;
  gravity_watt?: number | null;

  calibrated?: boolean | null;
  calibration_mae?: number | null;

  profile_used?: UnknownRecord | null;
  weather_used?: UnknownRecord | null;
}

/**
 * SessionReport – tåler HR-only / delvis data.
 * Dette er primærtypen som SessionView og api.ts bruker.
 */
export interface SessionReport extends UnknownRecord {
  /** Semver / schema id (kan mangle i mock eller eldre resultater) */
  schema_version?: string | null;

  /** Server-side id */
  session_id?: string | null;

  /** Strava / ride id */
  ride_id?: string | null;

  /** Starttid */
  start_time?: string | null;

  /** Distanse */
  distance_km?: number | null;

  /** Mode (om du har den) */
  mode?: SessionMode | null;

  /** Analyse-metrics */
  metrics?: SessionMetrics | null;

  /** Mange docs har “summary”/“profile”/“weather” osv – la de være åpne */
  summary?: UnknownRecord | null;
  profile?: UnknownRecord | null;
  weather?: UnknownRecord | null;
}
