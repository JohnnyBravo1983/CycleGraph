// src/mocks/sessionApi.ts
// Mock-API som henter fra /devdata/session_full_2h.json via fetch
// og mapper til et flatt SessionMetricsView.

import type {
  SessionMetricsView,
  SessionMetricsDoc,
} from "../types/SessionMetrics";
import {
  isSessionMetricsDoc,
  toSessionMetricsView,
} from "../types/SessionMetrics";

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}
function getStr(rec: Record<string, unknown>, key: string): string | undefined {
  const v = rec[key];
  return typeof v === "string" ? v : undefined;
}
function getNum(rec: Record<string, unknown>, key: string): number | null | undefined {
  const v = rec[key];
  return typeof v === "number" ? v : v === null ? null : undefined;
}
function getBool(rec: Record<string, unknown>, key: string): boolean | null | undefined {
  const v = rec[key];
  return typeof v === "boolean" ? v : v === null ? null : undefined;
}

function looksLikeFlatView(v: unknown): v is Partial<SessionMetricsView> & Record<string, unknown> {
  if (!isRecord(v)) return false;
  // Enkel heuristikk: har id eller session_id, og noen av feltene vi forventer
  const hasId = typeof v["id"] === "string" || typeof v["session_id"] === "string";
  const hasAnyMetric = "precision_watt" in v || "CdA" in v || "crr_used" in v || "publish_state" in v;
  return hasId && hasAnyMetric;
}

function toViewFromFlat(v: Partial<SessionMetricsView> & Record<string, unknown>): SessionMetricsView {
  const id = (typeof v.id === "string" && v.id) || getStr(v, "session_id") || "full2h";
  const savedAt = getStr(v, "saved_at") || new Date().toISOString();

  // Bygg et komplett view-objekt med sikre default-verdier:
  return {
    id,
    saved_at: savedAt,

    np: getNum(v, "np") ?? null,
    if_factor: getNum(v, "if_factor") ?? null,
    vi: getNum(v, "vi") ?? null,

    precision_watt: getNum(v, "precision_watt") ?? null,
    precision_watt_ci: Array.isArray(v.precision_watt_ci)
      ? (v.precision_watt_ci as [number, number])
      : null,

    crr_used: getNum(v, "crr_used") ?? null,
    CdA: getNum(v, "CdA") ?? null,
    reason: getStr(v, "reason") ?? null,

    rider_weight: getNum(v, "rider_weight") ?? null,
    bike_weight: getNum(v, "bike_weight") ?? null,
    bike_type: getStr(v, "bike_type") ?? null,
    tire_width: getNum(v, "tire_width") ?? null,
    tire_quality: getStr(v, "tire_quality") ?? null,

    publish_state:
      v.publish_state === "pending" ||
      v.publish_state === "done" ||
      v.publish_state === "failed" ||
      v.publish_state === null
        ? (v.publish_state as SessionMetricsView["publish_state"])
        : null,
    publish_hash: getStr(v, "publish_hash") ?? null,
    publish_time: getStr(v, "publish_time") ?? null,
    publish_error: getStr(v, "publish_error") ?? null,
    published_to_strava: getBool(v, "published_to_strava") ?? null,

    bike_name: getStr(v, "bike_name") ?? null,
    consent_accepted: getBool(v, "consent_accepted") ?? null,
    consent_version: getStr(v, "consent_version") ?? null,
    consent_time: getStr(v, "consent_time") ?? null,

    // Behold _raw hvis den faktisk er et SessionMetricsDoc, ellers en tom, trygg stub
    _raw:
      isSessionMetricsDoc((v as { _raw?: unknown })._raw)
        ? ((v as { _raw?: SessionMetricsDoc })._raw as SessionMetricsDoc)
        : ({
            schema_version: "0.7.3",
            session_id: id,
            saved_at: savedAt,
            metrics: {} as unknown,
            profile: {} as unknown,
          } as unknown as SessionMetricsDoc),
  };
}

/** Leser fixture fra public/devdata eller Vite dev-server */
async function loadFixtureUnknown(): Promise<unknown> {
  const res = await fetch("/devdata/session_full_2h.json", { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/** Plukker ut én post (matching på id/session_id) fra ulike mulige JSON-strukturer */
function pickCandidate(json: unknown, sessionId: string): unknown {
  if (Array.isArray(json)) {
    const found = json.find((item) => {
      if (!isRecord(item)) return false;
      const id =
        typeof item["id"] === "string"
          ? (item["id"] as string)
          : typeof item["session_id"] === "string"
          ? (item["session_id"] as string)
          : undefined;
      return id === sessionId;
    });
    return found ?? json[0];
  }
  // Hvis objekt med nested datafelt
  if (isRecord(json)) {
    // Vanligst: hele dokumentet eller allerede flat
    return json;
  }
  return null;
}

/** Hardkodet fallback hvis fixture ikke finnes eller ikke matcher */
function fallbackView(sessionId: string): SessionMetricsView {
  const now = new Date().toISOString();
  const id = sessionId || "full2h";
  return {
    id,
    saved_at: now,

    np: 255,
    if_factor: 0.84,
    vi: 1.05,

    precision_watt: 262.4,
    precision_watt_ci: [248.1, 276.3],

    crr_used: 0.0035,
    CdA: 0.29,
    reason: "outdoor_session",

    rider_weight: 93,
    bike_weight: 8.4,
    bike_type: "road",
    tire_width: 28,
    tire_quality: "good",

    publish_state: "done",
    publish_hash: "abc123",
    publish_time: now,
    publish_error: null,
    published_to_strava: true,

    bike_name: "Lapierre Pulsium",
    consent_accepted: true,
    consent_version: "1.0",
    consent_time: now,

    _raw: {
      schema_version: "0.7.3",
      session_id: id,
      saved_at: now,
      metrics: {} as unknown,
      profile: {} as unknown,
    } as unknown as SessionMetricsDoc,
  };
}

export async function getSessionMetricsById(sessionId: string): Promise<SessionMetricsView> {
  try {
    const json = await loadFixtureUnknown();
    const candidate = pickCandidate(json, sessionId);

    if (candidate && isSessionMetricsDoc(candidate)) {
      // Riktig nestet dokument → flatten
      const v = toSessionMetricsView(candidate);
      return { ...v, id: sessionId || v.id || "full2h" };
    }

    if (candidate && looksLikeFlatView(candidate)) {
      // Allerede "flat" struktur
      const v = toViewFromFlat(candidate);
      return { ...v, id: sessionId || v.id || "full2h" };
    }
  } catch {
    // fall through til fallback
  }

  return fallbackView(sessionId);
}
