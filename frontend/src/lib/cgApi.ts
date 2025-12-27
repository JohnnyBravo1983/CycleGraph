// frontend/src/lib/cgApi.ts

export type StatusResp = {
  ok: boolean;
  uid?: string;
  has_tokens?: boolean;
  expires_at?: number;
  expires_in_sec?: number;
  token_path?: string;
  redirect_uri_effective?: string;
  [k: string]: unknown;
};

export type ImportResp = {
  ok?: boolean;
  uid?: string;
  rid?: string;
  samples_len?: number;
  index_path?: string;
  index_rides_count?: number;
  analyze?: { status_code?: number; [k: string]: unknown };
  [k: string]: unknown;
};

export type SessionListItem = {
  session_id: string;
  ride_id: string;
  start_time?: string | null;
  distance_km?: number | null;
  precision_watt_avg?: number | null;
  profile_label?: string | null;
  weather_source?: string | null;
  debug_source_path?: string | null;
};

const BASE =
  (import.meta.env.VITE_BACKEND_URL as string | undefined) ??
  (import.meta.env.VITE_BACKEND_BASE as string | undefined) ??
  "http://localhost:5175";

/** Fjern trailing slash for robust sammensetting av URL-er */
function normalizeBase(url?: string): string | undefined {
  if (!url) return undefined;
  return String(url).replace(/\/+$/, "");
}

/**
 * Robust URL-builder:
 * - Tåler at BASE er "http://localhost:5175" ELLER "http://localhost:5175/api"
 * - Du kan alltid sende inn path som starter med "/api/..."
 */
function buildApiUrl(base: string, pathStartingWithApi: string): URL {
  const b = normalizeBase(base) ?? base;
  const baseEndsWithApi = b.endsWith("/api");

  // Hvis base allerede slutter på /api, fjern "/api" fra pathen for å unngå dobbel.
  const effectivePath = baseEndsWithApi
    ? pathStartingWithApi.replace(/^\/api\b/, "")
    : pathStartingWithApi;

  // Sørg for trailing slash i base når vi bruker URL-konstruktør med relativ path
  const baseForUrl = b.endsWith("/") ? b : `${b}/`;
  const rel = effectivePath.startsWith("/") ? effectivePath.slice(1) : effectivePath;

  return new URL(rel, baseForUrl);
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function extractErrorMessage(json: unknown): unknown {
  if (!isRecord(json)) return null;
  return (json as any).detail ??
    (json as any).reason ??
    (json as any).error ??
    (json as any).message ??
    null;
}

/**
 * Backend kan returnere:
 *  - Array: [...]
 *  - Objekt: { value: [...], Count: n } (eller lignende casing)
 */
function normalizeListAll(json: unknown): SessionListItem[] {
  // B) [...] (eldre/andre varianter)
  if (Array.isArray(json)) return json as SessionListItem[];

  // A) { value: [...], Count: n } (nåværende)
  if (json && typeof json === "object") {
    const v =
      (json as any).value ??
      (json as any).Value ??
      (json as any).items ??
      (json as any).Items ??
      (json as any).sessions ??
      (json as any).Sessions;

    if (Array.isArray(v)) return v as SessionListItem[];
  }

  return [];
}

async function cgFetchJson<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const base = normalizeBase(BASE) ?? "http://localhost:5175";
  const url = buildApiUrl(base, path);

  const res = await fetch(url.toString(), {
    ...init,
    credentials: "include", // ✅ KRITISK: alltid cookie
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
  });

  const text = await res.text().catch(() => "");

  let json: unknown = null;
  try {
    json = text ? (JSON.parse(text) as unknown) : null;
  } catch {
    json = null; // non-JSON
  }

  if (!res.ok) {
    const msgFromJson = extractErrorMessage(json);

    const msg =
      (typeof msgFromJson === "string" && msgFromJson) ||
      (msgFromJson ? JSON.stringify(msgFromJson) : null) ||
      (text ? text : null) ||
      `HTTP ${res.status} ${res.statusText}`;

    throw new Error(msg);
  }

  // hvis server svarer tomt men OK
  return (json ?? null) as T;
}

export const cgApi = {
  baseUrl: () => normalizeBase(BASE) ?? "http://localhost:5175",

  async status(): Promise<StatusResp> {
    return cgFetchJson<StatusResp>("/status", { method: "GET" });
  },

  async importRide(rid: string): Promise<ImportResp> {
    return cgFetchJson<ImportResp>(`/api/strava/import/${encodeURIComponent(rid)}`, {
      method: "POST",
      body: JSON.stringify({}), // backend forventer JSON
    });
  },

  // ✅ robust list/all: støtter array eller {value: [...], Count: n}
  async listAll(): Promise<SessionListItem[]> {
    const json = await cgFetchJson<unknown>("/api/sessions/list/all", { method: "GET" });
    return normalizeListAll(json);
  },
};
