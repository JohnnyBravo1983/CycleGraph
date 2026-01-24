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

// ✅ PATCH 1: legg til ProfileGetResp
export type ProfileGetResp = {
  ok?: boolean;
  profile_version?: string;
  version_hash?: string;
  profile?: Record<string, unknown>;
  [k: string]: unknown;
};

// ✅ PATCH: profileSave() typer
export type ProfileSaveResp = {
  profile?: Record<string, unknown>;
  profile_version?: string;
  version_hash?: string;
  version_at?: string;
  [k: string]: unknown;
};

export type ProfileSaveBody = Record<string, unknown> | { profile: Record<string, unknown> };

// ✅ PATCH: auth body
export type AuthBody = {
  email: string;
  password: string;
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
  if (!base) throw new Error("BASE URL is not defined");

  const cleanBase = base.replace(/\/+$/, "");
  const baseEndsWithApi = cleanBase.endsWith("/api");

  let effectivePath = pathStartingWithApi;
  if (baseEndsWithApi && pathStartingWithApi.startsWith("/api")) {
    effectivePath = pathStartingWithApi.replace(/^\/api/, "");
  }

  const fullPath = effectivePath.startsWith("/") ? effectivePath : "/" + effectivePath;
  return new URL(cleanBase + fullPath);
}

/**
 * ✅ FIX:
 * Bruk BACKEND BASE direkte (5175) i dev/test for å unngå "same-origin uten proxy".
 * I prod bruker vi VITE_BACKEND_URL/BASE eller default localhost.
 */
function baseUrl(): string {
  const b = normalizeBase(BASE) ?? "http://localhost:5175";
  return b;
}

/**
 * ✅ PATCH S2.5B-IMPORT-BASEURL:
 * Én SSOT for absolutt URL til backend API.
 * - Dev: BASE (typisk http://localhost:5175)
 * - Prod: kan være https://api.cyclegraph.app (via env), ellers fallback.
 */
function apiUrl(pathStartingWithApi: string): string {
  const b = baseUrl();
  return buildApiUrl(b, pathStartingWithApi).toString();
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function extractErrorMessage(json: unknown): unknown {
  if (!isRecord(json)) return null;
  return (json as any).detail ?? (json as any).reason ?? (json as any).error ?? (json as any).message ?? null;
}

/**
 * Backend kan returnere:
 *  - Array: [...]
 *  - Objekt: { value: [...], Count: n } (eller lignende casing)
 */
function normalizeListAll(json: unknown): SessionListItem[] {
  if (Array.isArray(json)) return json as SessionListItem[];

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

// ✅ PATCH 1 — cgApi: legg til ApiError (typed error for 409/400/etc)
class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function cgFetchJson<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const url = apiUrl(path);

  const res = await fetch(url, {
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
    json = null;
  }

  if (!res.ok) {
    const msgFromJson = extractErrorMessage(json);

    const msg =
      (typeof msgFromJson === "string" && msgFromJson) ||
      (msgFromJson ? JSON.stringify(msgFromJson) : null) ||
      (text ? text : null) ||
      `HTTP ${res.status} ${res.statusText}`;

    throw new ApiError(res.status, msg, json);
  }

  return (json ?? null) as T;
}

// ✅ PATCH 1: implementer profileGet() i samme stil (bruk apiUrl + include cookies)
async function profileGet(): Promise<ProfileGetResp> {
  const url = apiUrl("/api/profile/get");

  const res = await fetch(url, {
    method: "GET",
    credentials: "include",
    headers: { Accept: "application/json" },
  });

  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`profileGet failed ${res.status}: ${txt.slice(0, 200)}`);
  }

  return (await res.json()) as ProfileGetResp;
}

// ✅ PATCH: profileSave() (SSOT -> backend)
async function profileSave(body: ProfileSaveBody): Promise<ProfileSaveResp> {
  const url = apiUrl("/api/profile/save");
  console.log("[cgApi] profileSave →", url, body);

  const res = await fetch(url, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });

  console.log("[cgApi] profileSave status:", res.status, res.statusText);

  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`profileSave failed ${res.status}: ${txt.slice(0, 200)}`);
  }

  const json: unknown = await res.json().catch(() => null);
  console.log("[cgApi] profileSave raw JSON:", json);
  return (json ?? {}) as ProfileSaveResp;
}

// ✅ PATCH: authSignup/authLogin (for SignupPage.tsx)
async function authSignup(email: string, password: string): Promise<void> {
  await cgFetchJson<unknown>("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password } satisfies AuthBody),
  });
}

async function authLogin(email: string, password: string): Promise<void> {
  await cgFetchJson<unknown>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password } satisfies AuthBody),
  });
}

// ✅ PATCH 1: authMe() (DoD) — GET /api/auth/me
async function authMe(): Promise<unknown> {
  const url = apiUrl("/api/auth/me");
  console.log("[cgApi] authMe url =", url);
  return cgFetchJson<unknown>("/api/auth/me", { method: "GET" });
}

export const cgApi = {
  baseUrl: () => baseUrl(),

  async status(): Promise<StatusResp> {
    // NB: dette bruker "/status" som i din eksisterende backend (beholdt)
    return cgFetchJson<StatusResp>("/status", { method: "GET" });
  },

  // ✅ SSOT: Strava connected-status for current authed user
  async stravaStatus(): Promise<StatusResp> {
    return cgFetchJson<StatusResp>("/api/auth/strava/status", { method: "GET" });
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

  // ✅ AUTH
  authSignup,
  authLogin,
  authMe,

  // ✅ PROFILE
  profileGet,
  profileSave,
};

// (Valgfritt) eksportér ApiError hvis du vil mappe 409/400 i UI-lag
export { ApiError };
