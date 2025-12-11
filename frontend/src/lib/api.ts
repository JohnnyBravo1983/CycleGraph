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

    // 5) watts – bruk metrics.precision_watt hvis vi har det
    watts: Array.isArray(r.watts)
      ? r.watts
      : Array.isArray(metrics.precision_watt)
      ? metrics.precision_watt
      : Array.isArray(metrics.watts)
      ? metrics.watts
      : null,

    // 6) vind-relaterte felter – optional / nullable uansett
    wind_rel: r.wind_rel ?? metrics.wind_rel ?? null,
    v_rel: r.v_rel ?? metrics.v_rel ?? null,
  };

  return adapted;
}

/**
 * Hent en session:
 * - hvis id === "mock" → bruk mockSession (kilde: "mock")
 * - ellers krever vi VITE_BACKEND_URL og kaller POST {BASE}/sessions/{id}/analyze (kilde: "live")
 * Validerer alltid med Zod + semver.
 */
export async function fetchSession(id: string): Promise<FetchSessionResult> {
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
    console.error(
      "[API] fetchSession (LIVE) mangler VITE_BACKEND_URL for id=",
      id
    );
    return {
      ok: false,
      error:
        "Mangler backend-konfigurasjon (VITE_BACKEND_URL). Kan ikke hente økten fra server.",
      source: "live",
    };
  }

  // 3) LIVE-kall mot backend (analyze)
  // Merk: base forventes å allerede inkludere "/api" (f.eks. "http://localhost:5175/api")
  const url = `${base}/sessions/${encodeURIComponent(id)}/analyze`;
  console.log("[API] fetchSession (LIVE) →", url);

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      // analyze trenger egentlig ikke body, men noen backends liker eksplisitt {}
      body: JSON.stringify({}),
    });

    if (!res.ok) {
      const text = await safeReadText(res);
      console.error(
        "[API] fetchSession LIVE feilet:",
        res.status,
        res.statusText,
        text
      );
      return {
        ok: false,
        error: `Kunne ikke hente session analyze (${res.status} ${res.statusText})`,
        source: "live",
      };
    }

    const json = await parseJsonSafe(res);
    if (typeof json === "string") {
      console.error(
        "[API] fetchSession → backend svarte ikke med JSON",
        json
      );
      return {
        ok: false,
        error: "Kunne ikke parse JSON fra backend.",
        source: "live",
      };
    }

    // Ekstra logging av rå JSON fra backend
    console.log("[API] fetchSession LIVE raw JSON:", json);

    // 🔹 NYTT: tilpass backend-responsen til det schemaet vårt forventer
    const adaptedBase = adaptBackendSession(json);
    console.log("[API] fetchSession LIVE adapted for schema:", adaptedBase);

    const maybeInvalid =
      shouldSimulateInvalid() &&
      adaptedBase &&
      typeof adaptedBase === "object"
        ? invalidateSchemaForTest(adaptedBase)
        : adaptedBase;

    const parsed = safeParseSession(maybeInvalid);
    if (!parsed.ok) {
      console.error(
        "[API] fetchSession LIVE → schema-validering feilet",
        parsed.error
      );
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
// Sessions-list (/api/sessions/list)
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

type RawSession = {
  id?: string | number;
  session_id?: string | number;
  ride_id?: string | number;

  // mulige feltnavn for tid/dato
  start_time?: string | null;
  started_at?: string | null;
  start?: string | null;
  date?: string | null;

  // distanse
  distance_km?: number | null;
  distance?: number | null;
  distance_m?: number | null;

  // watt / precision
  precision_watt_avg?: number | null;
  avg_watt?: number | null;
  precision_watt?: number | null;
  metrics?: {
    precision_watt?: number | null;
  } | null;

  profile_label?: string | null;
  profile_used?: string | null;
  profile?: string | null;
  profile_version?: string | null; // 👈 lagt til

  weather_source?: string | null;
  weather?: { source?: string | null } | null;
};

export async function fetchSessionsList(): Promise<SessionListItem[]> {
  if (!BASE) {
    console.log(
      "[api.fetchSessionsList] Mangler VITE_BACKEND_URL – returnerer tom liste."
    );
    return [];
  }

  // Merk: backend-routen er /api/sessions/list
  const url = `${BASE}/sessions/list`;
  console.log("[API] fetchSessionsList →", url);

  let res: Response;
  try {
    res = await fetch(url);
  } catch (err) {
    console.error("[api.fetchSessionsList] Nettverksfeil:", err);
    return [];
  }

  console.log("[API] fetchSessionsList status:", res.status, res.statusText);

  if (!res.ok) {
    console.error(
      "[api.fetchSessionsList] Backend svarte ikke OK:",
      res.status,
      res.statusText
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

  const mapped: SessionListItem[] = rawList
    .map((raw, idx): SessionListItem | null => {
      const rideId = raw.ride_id ?? raw.session_id ?? raw.id;
      if (rideId === undefined || rideId === null) {
        console.warn(
          `[api.fetchSessionsList] Hopper over entry uten ride_id/session_id (index ${idx}):`,
          raw
        );
        return null;
      }

      // 🔹 Velg beste kandidat for start_time
      const startTime =
        raw.start_time ?? raw.started_at ?? raw.start ?? raw.date ?? null;

      // 🔹 Distanse: km hvis mulig, ellers m → km
      const distanceKm =
        typeof raw.distance_km === "number"
          ? raw.distance_km
          : typeof raw.distance === "number"
          ? raw.distance
          : typeof raw.distance_m === "number"
          ? raw.distance_m / 1000
          : null;

      // 🔹 Precision Watt snitt: prøv flere felter
      const precisionAvg =
        typeof raw.precision_watt_avg === "number"
          ? raw.precision_watt_avg
          : typeof raw.avg_watt === "number"
          ? raw.avg_watt
          : typeof raw.precision_watt === "number"
          ? raw.precision_watt
          : typeof raw.metrics?.precision_watt === "number"
          ? raw.metrics.precision_watt
          : null;

      const profileLabel =
        raw.profile_label ??
        raw.profile_used ??
        raw.profile ??
        raw.profile_version ?? // 👈 ny kandidat
        null;

      const weatherSource = raw.weather_source ?? raw.weather?.source ?? null;

      return {
        session_id: String(raw.session_id ?? rideId),
        ride_id: String(rideId),
        start_time: startTime,
        distance_km: distanceKm,
        precision_watt_avg: precisionAvg,
        profile_label: profileLabel,
        weather_source: weatherSource,
      };
    })
    .filter((x): x is SessionListItem => x !== null);

  console.log(
    `[api.fetchSessionsList] Mappet ${mapped.length} økter (fra ${rawList.length})`,
    mapped
  );

  return mapped;
}
