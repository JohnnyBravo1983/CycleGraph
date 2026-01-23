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

/**
 * 🔧 Sprint 4: Stabil cookie-binding (cg_uid)
 * Alle backend-kall SKAL sende cookies.
 */
const FETCH_WITH_COOKIES = {
  credentials: "include" as const,
};

/**
 * 🔧 Global helper (best-practice):
 * Sørger for at ALLE fetch-kall i denne fila alltid inkluderer cookies.
 * (Dette er patchen du ba om, men gjort én gang og riktig.)
 */
async function apiFetch(
  input: RequestInfo | URL,
  init: RequestInit = {}
): Promise<Response> {
  return fetch(input, {
    ...init,
    credentials: "include", // ✅ PATCH – SEND COOKIE (overstyrer evt. feil/utelatt credentials)
  });
}

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
  if (!base) {
    throw new Error("BASE URL is not defined");
  }
  
  const cleanBase = base.replace(/\/+$/, "");
  const baseEndsWithApi = cleanBase.endsWith("/api");
  let effectivePath = pathStartingWithApi;
  
  if (baseEndsWithApi && pathStartingWithApi.startsWith("/api")) {
    effectivePath = pathStartingWithApi.replace(/^\/api/, "");
  }
  
  const fullPath = effectivePath.startsWith("/") 
    ? effectivePath 
    : "/" + effectivePath;
  
  return new URL(cleanBase + fullPath);
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
    // ✅ PATCH: bruk apiFetch slik at også timeout-fetch alltid sender cookies
    const res = await apiFetch(input, { ...rest, signal: ac.signal });
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
    watts: Array.isArray(r.watts) ? r.watts : null,

    // 6) vind-relaterte felter – optional / nullable uansett
    wind_rel: r.wind_rel ?? metrics.wind_rel ?? null,
    v_rel: r.v_rel ?? metrics.v_rel ?? null,
  };

  return adapted;
}

/**
 * Sprint 3 Patch 3.2 — Tid/format (D4)
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

    const raw = shouldSimulateInvalid()
      ? invalidateSchemaForTest(mockSession)
      : mockSession;

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
      error:
        "Mangler backend-konfigurasjon (VITE_BACKEND_URL). Kan ikke hente økten fra server.",
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
    // ✅ PATCH: backend forventer payload med nøkkel "profile"
    // Prioritet: opts.profileOverride > localStorage override
    const profile =
      (opts?.profileOverride as Record<string, any> | undefined) ??
      (getLocalProfileOverride() as unknown as Record<string, any> | null) ??
      null;

    const bodyObj = profile ? { profile } : {};

    const res = await fetchWithTimeout(url.toString(), {
      ...FETCH_WITH_COOKIES, // ok å beholde, men apiFetch overstyrer uansett til include
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(bodyObj),
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

    console.log("[API] fetchSession LIVE raw JSON:", json);

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
// Sprint 4 Patch: støtt { value: [...] } OG [...]
// -----------------------------

export type SessionListItem = {
  session_id: string;
  ride_id: string;
  start_time: string | null;
  distance_km: number | null;
  precision_watt_avg: number | null;
  profile_label: string | null;
  weather_source: string | null;
};

// PATCH: Replace fetchSessionsList() komplett
export async function fetchSessionsList(): Promise<SessionListItem[]> {
  // ✅ PATCH 2 (KRITISK): dev = same-origin via Vite proxy, prod = absolutt base hvis mulig
  const url =
    import.meta.env.MODE !== "production"
      ? "/api/sessions/list/all"
      : buildApiUrl(normalizeBase(BASE) ?? "", "/api/sessions/list/all").toString();

  console.log("[API] fetchSessionsList →", url);

  // ✅ PATCH: dette fetch-kallet går via apiFetch → credentials: "include" alltid med
  const res = await apiFetch(url, {
    method: "GET",
  });

  console.log("[API] fetchSessionsList status:", res.status, res.statusText);
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`fetchSessionsList failed ${res.status}: ${txt.slice(0, 200)}`);
  }

  const json: unknown = await res.json();
  console.log("[API] fetchSessionsList raw JSON:", json);

  // ✅ Støtt både:
  // A) { value: [...], Count: n }
  // B) [...] (legacy)
  const rows: unknown[] = Array.isArray(json)
    ? json
    : Array.isArray((json as any)?.value)
      ? ((json as any).value as unknown[])
      : [];

  if (!Array.isArray(rows)) {
    console.warn(
      "[api.fetchSessionsList] Uventet format, forventet array eller {value: array}.",
      json
    );
    return [];
  }

  if (rows.length === 0) {
    console.warn("[api.fetchSessionsList] Ingen sessions i responsen.");
    return [];
  }

  const out: SessionListItem[] = [];

  for (const r of rows) {
    if (!r || typeof r !== "object") continue;
    const rec = r as any;

    // ✅ Definer eksplisitt (dette var mangelen hos deg)
    const session_id = rec.session_id != null ? String(rec.session_id) : null;
    const ride_id = rec.ride_id != null ? String(rec.ride_id) : null;

    if (!session_id || !ride_id) continue;

    out.push({
      session_id,
      ride_id,
      start_time: rec.start_time != null ? String(rec.start_time) : null,
      distance_km:
        typeof rec.distance_km === "number"
          ? rec.distance_km
          : rec.distance_km != null
            ? Number(rec.distance_km)
            : null,
      precision_watt_avg:
        typeof rec.precision_watt_avg === "number"
          ? rec.precision_watt_avg
          : rec.precision_watt_avg != null
            ? Number(rec.precision_watt_avg)
            : null,
      profile_label: rec.profile_label != null ? String(rec.profile_label) : null,
      weather_source: rec.weather_source != null ? String(rec.weather_source) : null,
    });
  }

  if (!out.length) {
    console.warn(
      "[api.fetchSessionsList] Rader fantes, men ingen kunne normaliseres trygt.",
      { rows_len: rows.length, sample: rows[0] }
    );
    return [];
  }

  // ✅ DEBUG: eksponer formatter for DevTools (kun i DEV)
  if (import.meta.env.DEV) {
    (window as any).formatStartTimeForUi = formatStartTimeForUi;
  }

  return out;
}
