// frontend/src/lib/api.ts
import type { SessionReport } from "../types/session";
import { mockSession } from "../mocks/mockSession";
import { safeParseSession, ensureSemver } from "./schema";

/** Result-typer beholdt som hos deg */
type Ok = { ok: true; data: SessionReport; source: "mock" | "live" };
type Err = { ok: false; error: string; source?: "mock" | "live" };
export type FetchSessionResult = Ok | Err;

// Hent Vite-variabler (.env.local). Hvis BASE mangler → vi faller til mock-kilde.
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

/**
 * Hent en session:
 * - hvis BASE mangler eller id === "mock" → bruk mockSession (kilde: "mock")
 * - ellers → POST {BASE}/api/sessions/{id}/analyze (kilde: "live")
 * Validerer alltid med Zod + semver.
 */
export async function fetchSession(id: string): Promise<FetchSessionResult> {
  const base = normalizeBase(BASE);

  // MOCK eller manglende BASE → mock-kilde
  if (!base || id === "mock") {
    console.warn(
      "[API] fetchSession → bruker mockSession (ingen backend eller id === 'mock')"
    );

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

    try {
      ensureSemver(parsed.data.schema_version);
    } catch (e) {
      return {
        ok: false,
        error:
          e instanceof Error
            ? e.message
            : "Ugyldig schema_version i mock-data.",
        source: "mock",
      };
    }

    return { ok: true, data: parsed.data, source: "mock" };
  }

  const url = `${base}/api/sessions/${encodeURIComponent(id)}/analyze`;
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

    const maybeInvalid =
      shouldSimulateInvalid() && json && typeof json === "object"
        ? invalidateSchemaForTest(json)
        : json;

    const parsed = safeParseSession(maybeInvalid);
    if (!parsed.ok) {
      console.error(
        "[API] fetchSession → safeParseSession feilet",
        parsed.error
      );
      return {
        ok: false,
        error: `Ugyldig session-format fra backend: ${parsed.error}`,
        source: "live",
      };
    }

    try {
      ensureSemver(parsed.data.schema_version);
    } catch (e) {
      return {
        ok: false,
        error:
          e instanceof Error
            ? e.message
            : "Ugyldig schema_version i backend-respons.",
        source: "live",
      };
    }

    return {
      ok: true,
      data: parsed.data,
      source: "live",
    };
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error("[API] fetchSession → exception:", msg);
    return {
      ok: false,
      error: msg,
      source: "live",
    };
  }
}

// ---------------------------------------------------------------------------
// SESSIONS (fra /api/sessions/list)
// ---------------------------------------------------------------------------

export type SessionSummary = {
  id: string;

  // Profil og vær slik backend rapporterer det
  profile_version?: string | null;
  weather_source?: string | null;

  // Ferdig label vi kan vise i UI
  profile_label?: string | null;

  // Reservert til senere når backend/summary.csv gir oss mer
  start_time?: string | null;
  precision_watt_avg?: number | null;
  distance_km?: number | null;
};

export async function fetchSessionsList(): Promise<SessionSummary[]> {
  const base = normalizeBase(BASE);
  if (!base) {
    console.warn("[API] VITE_BACKEND_URL mangler → tom sessions-liste");
    return [];
  }

  const url = `${base}/api/sessions/list`;
  console.log("[API] fetchSessionsList →", url);

  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(
      `Kunne ikke hente sessions list (${res.status} ${res.statusText})`
    );
  }

  const rawJson = await res.json();

  if (!Array.isArray(rawJson)) {
    console.error("[API] /api/sessions/list svarte ikke med liste", rawJson);
    throw new Error("Ugyldig svar fra /api/sessions/list");
  }

  if (rawJson.length > 0) {
    console.log("[API] /api/sessions/list example row:", rawJson[0]);
  }

  const mapped: SessionSummary[] = (rawJson as unknown[])
    .map((row): SessionSummary | null => {
      if (typeof row !== "object" || row === null) {
        console.warn(
          "[API] droppet rad som ikke er objekt i /api/sessions/list",
          row
        );
        return null;
      }

      const obj = row as Record<string, unknown>;

      const rawId =
        obj["id"] ??
        obj["ride_id"] ?? // dette har vi sett i output
        obj["sid"] ??
        obj["session_id"] ??
        obj["activity_id"] ??
        obj["strava_id"];

      if (!rawId) {
        console.warn("[API] droppet rad uten id i /api/sessions/list", obj);
        return null;
      }

      const profile_version =
        typeof obj["profile_version"] === "string"
          ? (obj["profile_version"] as string)
          : null;

      const weather_source =
        typeof obj["weather_source"] === "string"
          ? (obj["weather_source"] as string)
          : null;

      const profile_label =
        profile_version && weather_source
          ? `${profile_version} – vær: ${weather_source}`
          : profile_version ?? weather_source ?? null;

      return {
        id: String(rawId),
        profile_version,
        weather_source,
        profile_label,
        start_time: null,
        precision_watt_avg: null,
        distance_km: null,
      };
    })
    .filter((x): x is SessionSummary => x !== null);

  console.log("[API] fetchSessionsList →", mapped.length, "økter");
  return mapped;
}
