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

export type ProfileSaveBody =
  | Record<string, unknown>
  | { profile: Record<string, unknown> };

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

// ✅ liten helper så patchen kan bruke baseUrl() uten å være avhengig av cgApi-objektet
function baseUrl(): string {
  return normalizeBase(BASE) ?? "http://localhost:5175";
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function extractErrorMessage(json: unknown): unknown {
  if (!isRecord(json)) return null;
  return (
    (json as any).detail ??
    (json as any).reason ??
    (json as any).error ??
    (json as any).message ??
    null
  );
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

// ✅ PATCH 1: implementer profileGet() i samme stil (bruker buildApiUrl + include cookies)
async function profileGet(): Promise<ProfileGetResp> {
  const base = normalizeBase(BASE) ?? "http://localhost:5175";
  const url = buildApiUrl(base, "/api/profile/get");

  const res = await fetch(url.toString(), {
    method: "GET",
    credentials: "include",
    headers: {
      Accept: "application/json",
    },
  });

  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`profileGet failed ${res.status}: ${txt.slice(0, 200)}`);
  }

  return (await res.json()) as ProfileGetResp;
}

// ✅ PATCH: profileSave() (SSOT -> backend)
async function profileSave(body: ProfileSaveBody): Promise<ProfileSaveResp> {
  const base = baseUrl();
  const url = buildApiUrl(base, "/api/profile/save");
  console.log("[cgApi] profileSave →", url.toString(), body);

  const res = await fetch(url.toString(), {
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
  // bruker cgFetchJson for konsistent error-handling + credentials: include
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

export const cgApi = {
  baseUrl: () => baseUrl(),

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

  // ✅ AUTH (NYTT)
  authSignup,
  authLogin,

  // ✅ PATCH 1: eksporter profileGet
  profileGet,

  // ✅ PATCH: eksporter profileSave
  profileSave,
};
