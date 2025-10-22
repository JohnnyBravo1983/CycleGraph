// src/types/SessionMetrics.ts
// Deklarasjoner i tråd med schemas/session_metrics.schema.json (v0.7.3)

export type NullableNumber = number | null;
export type NullableString = string | null;
export type NullableBoolean = boolean | null;

export type PublishState = 'pending' | 'done' | 'failed' | null;

export interface SessionMetricsBlock {
  // HOVEDMETRICS
  np: NullableNumber;
  if_factor: NullableNumber;
  vi: NullableNumber;

  precision_watt: NullableNumber;
  precision_watt_ci: [number, number] | null;

  crr_used: NullableNumber;
  CdA: NullableNumber;
  reason: NullableString;

  rider_weight: NullableNumber;
  bike_weight: NullableNumber;
  bike_type: NullableString;
  tire_width: NullableNumber;
  tire_quality: NullableString;

  // PUBLISH
  publish_state: PublishState;
  publish_hash: NullableString;
  publish_time: NullableString;   // ISO datetime (eller null)
  publish_error: NullableString;

  published_to_strava: NullableBoolean;

  // schema sier additionalProperties: true
  [k: string]: unknown;
}

export interface SessionProfileBlock {
  consent_accepted: NullableBoolean;
  consent_version: NullableString;
  consent_time: NullableString;   // ISO datetime (eller null)
  bike_name: NullableString;

  // schema sier additionalProperties: true
  [k: string]: unknown;
}

export interface SessionMetricsDoc {
  schema_version: '0.7.3';
  session_id: string;
  saved_at: string;               // ISO datetime
  metrics: SessionMetricsBlock;
  profile: SessionProfileBlock;

  // schema sier additionalProperties: true
  [k: string]: unknown;
}

/* ────────────────────────────────────────────────────────────────────────────
   Hjelpere for praktisk bruk i UI
   - CI-normalisering
   - "Flatten" til et View-objekt hvis du vil slippe metrics/profile-nesting
   ───────────────────────────────────────────────────────────────────────── */

export function normalizePwCI(
  ci: SessionMetricsBlock['precision_watt_ci']
): { low?: number; high?: number } {
  if (!ci) return {};
  const [low, high] = ci;
  return { low, high };
}

/** Flatt view som er lett å mate inn i komponenter uten å bry seg om nesting */
export interface SessionMetricsView {
  id: string;
  saved_at: string;

  // metrics
  np: NullableNumber;
  if_factor: NullableNumber;
  vi: NullableNumber;

  precision_watt: NullableNumber;
  precision_watt_ci: [number, number] | null;

  crr_used: NullableNumber;
  CdA: NullableNumber;
  reason: NullableString;

  rider_weight: NullableNumber;
  bike_weight: NullableNumber;
  bike_type: NullableString;
  tire_width: NullableNumber;
  tire_quality: NullableString;

  publish_state: PublishState;
  publish_hash: NullableString;
  publish_time: NullableString;
  publish_error: NullableString;
  published_to_strava: NullableBoolean;

  // profile (typisk visning)
  bike_name: NullableString;
  consent_accepted: NullableBoolean;
  consent_version: NullableString;
  consent_time: NullableString;

  // Behold original for debugging/videre bruk
  _raw: SessionMetricsDoc;
}

/** Gjør om dokumentet fra backend til et flatt view-objekt for UI */
export function toSessionMetricsView(doc: SessionMetricsDoc): SessionMetricsView {
  const m = doc.metrics ?? ({} as SessionMetricsBlock);
  const p = doc.profile ?? ({} as SessionProfileBlock);
  return {
    id: doc.session_id,
    saved_at: doc.saved_at,

    np: m.np ?? null,
    if_factor: m.if_factor ?? null,
    vi: m.vi ?? null,

    precision_watt: m.precision_watt ?? null,
    precision_watt_ci: m.precision_watt_ci ?? null,

    crr_used: m.crr_used ?? null,
    CdA: m.CdA ?? null,
    reason: m.reason ?? null,

    rider_weight: m.rider_weight ?? null,
    bike_weight: m.bike_weight ?? null,
    bike_type: m.bike_type ?? null,
    tire_width: m.tire_width ?? null,
    tire_quality: m.tire_quality ?? null,

    publish_state: m.publish_state ?? null,
    publish_hash: m.publish_hash ?? null,
    publish_time: m.publish_time ?? null,
    publish_error: m.publish_error ?? null,
    published_to_strava: m.published_to_strava ?? null,

    bike_name: p.bike_name ?? null,
    consent_accepted: p.consent_accepted ?? null,
    consent_version: p.consent_version ?? null,
    consent_time: p.consent_time ?? null,

    _raw: doc,
  };
}

/** Type guard for å verifisere at objektet ser ut som et SessionMetricsDoc */
export function isSessionMetricsDoc(x: unknown): x is SessionMetricsDoc {
  if (!x || typeof x !== "object") return false;
  const obj = x as Partial<SessionMetricsDoc>;

  return (
    obj.schema_version === "0.7.3" &&
    typeof obj.session_id === "string" &&
    typeof obj.saved_at === "string" &&
    obj.metrics !== undefined &&
    typeof obj.metrics === "object" &&
    obj.profile !== undefined &&
    typeof obj.profile === "object"
  );
}
