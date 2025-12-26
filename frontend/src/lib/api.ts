// frontend/src/lib/api.ts
import type { SessionReport } from "../types/session";
import { mockSession } from "../mocks/mockSession";
import { safeParseSession, ensureSemver } from "./schema";

/** Result-typer beholdt som hos deg */
type Ok = { ok: true; data: SessionReport; source: "mock" | "live" };
type Err = { ok: false; error: string; source?: "mock" | "live" };
export type FetchSessionResult = Ok | Err;

// Hent Vite-variabler (.env.local).
const BASE = import.meta.env.VITE_BACKEND_URL as string | undefined;

/** Fjern trailing slash for robust sammensetting av URL-er */
function normalizeBase(url?: string): string | undefined {
  if (!url) return undefined;
  return url.replace(/\/+$/, "");
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

type FetchSessionOpts = {
  forceRecompute?: boolean;
  profileOverride?: Record<string, any>;
};

/**
 * Hent profile override fra localStorage.
 * Robust: støtter både "draft" og "profile"-objekt, samt direkte profilform.
 * Returnerer null hvis profilen ikke ser "ferdig" ut (krever 4 finite tall).
 */
function getLocalProfileOverride(): {
  weight_kg: number;
  cda: number;
  crr: number;
  crank_efficiency: number;
} | null {
  try {
    const raw = localStorage.getItem("cg.profile.v1");
    if (!raw) return null;
    const p = JSON.parse(raw);

    // Støtter både "draft" og "profile"-objekt (robust)
    const src = p?.weight_kg !== undefined ? p : p?.profile ?? p?.draft ?? p;

    const weight_kg = Number(src?.weight_kg);
    const cda = Number(src?.cda);
    const crr = Number(src?.crr);
    const crank_efficiency = Number(src?.crank_efficiency);

    // returner null hvis dette ikke ser ut som en profil ennå
    if (
      !Number.isFinite(weight_kg) ||
      !Number.isFinite(cda) ||
      !Number.isFinite(crr) ||
      !Number.isFinite(crank_efficiency)
    ) {
      return null;
    }

    return { weight_kg, cda, crr, crank_efficiency };
  } catch {
    return null;
  }
}

/** Dev-bryter: ?simulateInvalid i URL for å teste ugyldig/manglende schema_version */
function shouldSimulateInvalid(): boolean {
  try {
    const qs = new URLSearchParams(window.location.search);
    return qs.has("simulateInvalid");
  } catch {
    return false;
  }
}

/** Fjern schema_version for å trigge valideringsfeil i dev */
function invalidateSchemaForTest<T>(obj: T): T {
  const rec = { ...(obj as unknown as Record<string, unknown>) };
  delete rec["schema_version"];
  return rec as unknown as T;
}

/** Abort/timeout-wrapper for fetch (ingen eksterne libs) */
export async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit & { timeoutMs?: number } = {}
): Promise<Response> {
  const { timeoutMs = 10_000, signal, ...rest } = init;

  const ac = new AbortController();
  const timeoutId = setTimeout(() => ac.abort(), timeoutMs);

  // Kobler evt. ekstern AbortSignal til vår controller
  if (signal) {
    if (signal.aborted) ac.abort();
    else signal.addEventListener("abort", () => ac.abort(), { once: true });
  }

  try {
    const res = await fetch(input, { ...rest, signal: ac.signal });
    return res;
  } catch (err: unknown) {
    const isAbort =
      typeof err === "object" &&
      err !== null &&
      "name" in err &&
      (err as { name?: unknown }).name === "AbortError";

    if (isAbort) {
      throw new Error("Tidsavbrudd: forespørselen tok for lang tid.");
    }
    throw err instanceof Error ? err : new Error(String(err));
  } finally {
    clearTimeout(timeoutId);
  }
}

/** Trygg JSON-parsing: returnerer string hvis ikke gyldig JSON (for feilmeldinger) */
export async function parseJsonSafe(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text; // råtekst ved ikke-JSON svar
  }
}

/** Les feilkropp som tekst uten å kaste videre feil */
async function safeReadText(res: Response): Promise<string> {
  try {
    return await res.text();
  } catch {
    return "";
  }
}

// Hjelpefunksjon: gjør backend-responsen mer "schema-vennlig"
function adaptBackendSession(raw: unknown): any {
  if (!raw || typeof raw !== "object") return raw;

  const r = raw as any;
  const metrics = r.metrics ?? {};
  const debug = r.debug ?? {};

  const adapted: any = {
    // behold alt originalt
    ...r,

    // 1) sørg for at schema_version alltid er en streng (ellers setter vi en dummy-verdi)
    schema_version:
      typeof r.schema_version === "string"
        ? r.schema_version
        : typeof metrics.schema_version === "string"
        ? metrics.schema_version
        : typeof debug.schema_version === "string"
        ? debug.schema_version
        : "0.0.0",

    // 2) gjennomsnittspuls – prøv flere steder, default null
    avg_hr:
      typeof r.avg_hr === "number"
        ? r.avg_hr
        : typeof metrics.avg_hr === "number"
        ? metrics.avg_hr
        : typeof debug.avg_hr === "number"
        ? debug.avg_hr
        : null,

    // 3) calibrated må være boolean for Zod → default false hvis ikke satt
    calibrated:
      typeof r.calibrated === "boolean"
        ? r.calibrated
        : typeof metrics.calibrated === "boolean"
        ? metrics.calibrated
        : false,

    // 4) status – prøv noen fallback-kilder
    status:
      typeof r.status === "string"
        ? r.status
        : typeof metrics.status === "string"
        ? metrics.status
        : typeof debug.status === "string"
        ? debug.status
        : typeof r.source === "string"
        ? r.source
        : "ok",

    // 5) watts – Sprint 3 strict: ingen metrics-fallback i UI-kontrakt
    // Hvis backend sender r.watts som array, kan vi bruke den (detail/debug).
    // Ellers: null (ikke “finne på” fra metrics).
    watts: Array.isArray(r.watts) ? r.watts : null,

    // 6) vind-relaterte felter – optional / nullable uansett
    wind_rel: r.wind_rel ?? metrics.wind_rel ?? null,
    v_rel: r.v_rel ?? metrics.v_rel ?? null,
  };

  return adapted;
}

/**
 * Sprint 3 Patch 3.2 — Tid/format (D4)
 * - Hvis start_time = "YYYY-MM-DD" -> vis kun dato (lokal), f.eks "22.11.2025"
 * - Hvis ISO datetime -> vis "dd.mm.yyyy HH:MM" (lokalt)
 * Viktig: Ingen gjetting på UTC vs lokal; vi bare presenterer stabilt.
 */
export function formatStartTimeForUi(start_time: string | null | undefined): string {
  if (!start_time) return "";

  const s = String(start_time).trim();
  if (!s) return "";

  // 1) dato-only: YYYY-MM-DD
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (m) {
    const yyyy = Number(m[1]);
    const mm = Number(m[2]);
    const dd = Number(m[3]);
    if (
      Number.isFinite(yyyy) &&
      Number.isFinite(mm) &&
      Number.isFinite(dd) &&
      mm >= 1 &&
      mm <= 12 &&
      dd >= 1 &&
      dd <= 31
    ) {
      const d = new Date(yyyy, mm - 1, dd);
      return new Intl.DateTimeFormat(undefined, {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      }).format(d);
    }
    return s;
  }

  // 2) ISO datetime → vis MED sekunder
  const d = new Date(s);
  if (!Number.isNaN(d.getTime())) {
    return new Intl.DateTimeFormat(undefined, {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(d);
  }

  // 3) fallback
  return s;
}

  

 

/**
 * Hent en session:
 * - hvis id === "mock" → bruk mockSession (kilde: "mock")
 * - ellers krever vi VITE_BACKEND_URL og kaller POST {BASE}/api/sessions/{id}/analyze (kilde: "live")
 * Validerer alltid med Zod + semver.
 */
export async function fetchSession(
  id: string,
  opts?: FetchSessionOpts
): Promise<FetchSessionResult> {
  const base = normalizeBase(BASE);

  // 1) Eksplisitt mock-modus: /session/mock
  if (id === "mock") {
    console.warn("[API] fetchSession → bruker mockSession (id === 'mock')");

    const raw = shouldSimulateInvalid() ? invalidateSchemaForTest(mockSession) : mockSession;

    const parsed = safeParseSession(raw);
    if (!parsed.ok) {
      return {
        ok: false,
        error: `Mock-data validerte ikke: ${parsed.error}`,
        source: "mock",
      };
    }

    // 👇 Semver-avvik i mock gir bare warning, ikke feil
    try {
      ensureSemver(parsed.data.schema_version as string | undefined);
    } catch (e) {
      console.warn(
        "[API] fetchSession MOCK → uventet schema_version, fortsetter likevel:",
        (e as Error).message
      );
    }

    return { ok: true, data: parsed.data, source: "mock" };
  }

  // 2) For alle "ekte" id-er krever vi backend-URL
  if (!base) {
    console.error("[API] fetchSession (LIVE) mangler VITE_BACKEND_URL for id=", id);
    return {
      ok: false,
      error: "Mangler backend-konfigurasjon (VITE_BACKEND_URL). Kan ikke hente økten fra server.",
      source: "live",
    };
  }

  // 3) LIVE-kall mot backend (analyze)
  const url = buildApiUrl(base, `/api/sessions/${encodeURIComponent(id)}/analyze`);

  if (opts?.forceRecompute) {
    url.searchParams.set("force_recompute", "1");
  }

  console.log("[API] fetchSession (LIVE) →", url.toString());

  try {
    // Default: eksisterende body (beholdt minimalistisk)
    const body: Record<string, any> = {};

    // Prioritet: opts.profileOverride > localStorage override
    const profile_override = opts?.profileOverride ?? getLocalProfileOverride() ?? null;

    const payload = profile_override != null ? { ...body, profile_override } : { ...body };

    const res = await fetchWithTimeout(url.toString(), {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      timeoutMs: 20_000,
    });

    if (!res.ok) {
      const text = await safeReadText(res);
      console.error("[API] fetchSession LIVE feilet:", res.status, res.statusText, text);
      return {
        ok: false,
        error: `Kunne ikke hente session analyze (${res.status} ${res.statusText})`,
        source: "live",
      };
    }

    const json = await parseJsonSafe(res);
    if (typeof json === "string") {
      console.error("[API] fetchSession → backend svarte ikke med JSON", json);
      return {
        ok: false,
        error: "Kunne ikke parse JSON fra backend.",
        source: "live",
      };
    }

    // Ekstra logging av rå JSON fra backend
    console.log("[API] fetchSession LIVE raw JSON:", json);

    // 🔹 Tilpass backend-responsen til det schemaet vårt forventer
    const adaptedBase = adaptBackendSession(json);
    console.log("[API] fetchSession LIVE adapted for schema:", adaptedBase);

    const maybeInvalid =
      shouldSimulateInvalid() && adaptedBase && typeof adaptedBase === "object"
        ? invalidateSchemaForTest(adaptedBase)
        : adaptedBase;

    const parsed = safeParseSession(maybeInvalid);
    if (!parsed.ok) {
      console.error("[API] fetchSession LIVE → schema-validering feilet", parsed.error);
      return {
        ok: false,
        error: `Backend-data validerte ikke: ${parsed.error}`,
        source: "live",
      };
    }

    const session = parsed.data;

    // 🔹 Vi sjekker fortsatt schema_version, men lar det være en WARNING
    try {
      ensureSemver(session.schema_version as string | undefined);
    } catch (err) {
      console.warn(
        "[API] fetchSession LIVE → uventet schema_version, fortsetter likevel:",
        String((err as Error)?.message ?? err)
      );
    }

    return { ok: true, data: session, source: "live" };
  } catch (err) {
    console.error("[API] fetchSession LIVE → nettverks-/runtime-feil:", err);
    return {
      ok: false,
      error: "Klarte ikke å hente økten fra backend.",
      source: "live",
    };
  }
}

// -----------------------------
// Sessions-list (/api/sessions/list/all)
// Sprint 3 Patch 3.1 — Strict summary contract
// -----------------------------

export type SessionListItem = {
  session_id: string;
  ride_id: string;
  start_time: string | null; // strict: kun raw.start_time
  distance_km: number | null;
  precision_watt_avg: number | null; // strict: kun raw.precision_watt_avg
  profile_label: string | null;
  weather_source: string | null;
};

type RawSession = {
  // strict contract: vi forventer session_id, men lar types være litt robuste for parsing
  session_id?: string | number | null;
  ride_id?: string | number | null;

  // strict contract: kun start_time
  start_time?: string | null;

  // behold disse hvis UI bruker dem (men ikke “gjetting”)
  distance_km?: number | null;
  profile_label?: string | null;
  weather_source?: string | null;

  // eksplisitt: ignorert i strict mapping (ikke bruk!)
  // started_at?: string | null;
  // start?: string | null;
  // date?: string | null;
  // metrics?: any;
};

function toSessionListItemStrict(raw: RawSession, idx: number): SessionListItem | null {
  const sid = raw?.session_id;

  // ✅ Strict: id/sid i frontend = raw.session_id (ingen fallback til ride_id/id/sid)
  if (sid === null || sid === undefined || String(sid).trim() === "") {
    console.warn(
      `[api.fetchSessionsList] Strict: hopper over entry uten session_id (index ${idx}):`,
      raw
    );
    return null;
  }

  const session_id = String(sid);

  // ✅ ride_id beholdes (kan være null i backend, da setter vi lik session_id)
  const ride_id =
    raw.ride_id !== null && raw.ride_id !== undefined && String(raw.ride_id).trim() !== ""
      ? String(raw.ride_id)
      : session_id;

  // ✅ Strict: start_time = raw.start_time ?? null (ingen fallback)
  const start_time = raw.start_time ?? null;

  // ✅ Strict: precision_watt_avg = raw.precision_watt_avg (ingen metrics fallback)
  const precision_watt_avg =
    typeof (raw as any).precision_watt_avg === "number" ? (raw as any).precision_watt_avg : null;

  // ✅ behold disse hvis UI bruker dem, men uten å “finne på” andre felter
  const distance_km = typeof raw.distance_km === "number" ? raw.distance_km : null;
  const profile_label = raw.profile_label ?? null;
  const weather_source = raw.weather_source ?? null;

  return {
    session_id,
    ride_id,
    start_time,
    distance_km,
    precision_watt_avg,
    profile_label,
    weather_source,
  };
}

export async function fetchSessionsList(): Promise<SessionListItem[]> {
  const base = normalizeBase(BASE);
  if (!base) {
    console.log("[api.fetchSessionsList] Mangler VITE_BACKEND_URL – returnerer tom liste.");
    return [];
  }


// ✅ Bruk robust URL-builder (tåler BASE med /api)
const url = buildApiUrl(base, "/api/sessions/list/all");
console.log("[API] fetchSessionsList →", url.toString());

let res: Response;
try {
  res = await fetchWithTimeout(url.toString(), { timeoutMs: 15_000 });
} catch (err) {
  console.error("[api.fetchSessionsList] Nettverksfeil:", err);
  return [];
}

console.log("[API] fetchSessionsList status:", res.status, res.statusText);

if (!res.ok) {
  const text = await safeReadText(res);
  console.error(
    "[api.fetchSessionsList] Backend svarte ikke OK:",
    res.status,
    res.statusText,
    text
  );
  return [];
}

let json: unknown;
try {
  json = await res.json();
} catch (err) {
  console.error("[api.fetchSessionsList] Klarte ikke å parse JSON:", err);
  return [];
}

console.log("[API] fetchSessionsList raw JSON:", json);

// Støtt både:
// 1) [ { ... }, { ... } ]
// 2) { sessions: [ ... ] }
const rawList: RawSession[] = Array.isArray(json)
  ? (json as RawSession[])
  : json &&
    typeof json === "object" &&
    Array.isArray((json as { sessions?: unknown }).sessions)
  ? ((json as { sessions: RawSession[] }).sessions)
  : [];

if (!Array.isArray(rawList) || rawList.length === 0) {
  console.warn("[api.fetchSessionsList] Ingen sessions i responsen.");
  return [];
}

// ✅ Strict summary mapping
const mapped: SessionListItem[] = rawList
  .map((raw, idx) => toSessionListItemStrict(raw, idx))
  .filter((x): x is SessionListItem => x !== null);

console.log(
  `[api.fetchSessionsList] Strict mappet ${mapped.length} økter (fra ${rawList.length})`,
  mapped
);

// ✅ DEBUG: eksponer formatter for DevTools (kun i DEV)
if (import.meta.env.DEV) {
  (window as any).formatStartTimeForUi = formatStartTimeForUi;
}

return mapped;
}
