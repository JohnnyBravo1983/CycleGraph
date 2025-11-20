// frontend/src/lib/api.ts
import type { SessionReport, SessionInfo } from "../types/session";
import { mockSession } from "../mocks/mockSession";
import {
  safeParseSession,
  ensureSemver,
  type AnalyzeResponse,
  type Profile,
  type TrendSummary,
  type TrendPivot,
  type CsvRows,
} from "./schema";
import { fetchJSON } from "./fetchJSON";

// Les Vite-ENV trygt uten å være bundet til ImportMetaEnv-typen
type ViteEnv = Record<string, string | undefined>;

function readViteEnv(): ViteEnv {
  return (
    (typeof import.meta !== "undefined"
      ? (import.meta as unknown as { env?: ViteEnv }).env
      : undefined) ?? {}
  );
}

const viteEnv = readViteEnv();

// Forventer at VITE_BACKEND_URL ≈ "http://127.0.0.1:5175"
// Vi legger selv på /api i BACKEND_BASE (brukes bl.a. for CSV).
const BACKEND_BASE =
  (viteEnv.VITE_BACKEND_URL || "http://127.0.0.1:5175") + "/api";

// Legacy analyze_session bruker BASE uten /api og legger det selv på i URL-byggeren
const BASE = viteEnv.VITE_BACKEND_URL || "http://127.0.0.1:5175";

/** Result-typer beholdt som hos deg */
type Ok = { ok: true; data: SessionReport; source: "mock" | "live" };
type Err = { ok: false; error: string; source?: "mock" | "live" };
export type FetchSessionResult = Ok | Err;

/** Fjern trailing slash for robust sammensetting av URL-er */
function normalizeBase(url?: string): string | undefined {
  if (!url) return undefined;
  return url.replace(/\/+$/, "");
}

/** Liten hjelp for realisme i mock */
const delay = (ms: number) => new Promise((res) => setTimeout(res, ms));

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
    const res = await fetch(input, {
      ...rest,
      signal: ac.signal,
      credentials: rest.credentials ?? "include",
    });
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

/** Bygg URL til analyze_session (legacy) */
function buildAnalyzeUrl(base: string, id: string): string {
  return `${base}/api/analyze_session?id=${encodeURIComponent(id)}`;
}

// CSV header-normalisering for trend/summary.csv
const TREND_SUMMARY_HEADER =
  "session_id,date,avg_watt,w_per_beat,cgs,avg_hr,mode,profile_version,pw_quality,calibrated";

export function normalizeSummaryCsv(path: string, raw: string): string {
  if (!path.includes("summary.csv")) return raw;

  console.log("[API] normalizeSummaryCsv aktiv", {
    path,
    sample: raw.slice(0, 80),
  });

  const trimmed = raw.replace(/\r\n/g, "\n").trim();
  if (!trimmed) return trimmed;

  // 1) Sørg for header
  let withHeader: string;
  if (trimmed.startsWith("session_id,")) {
    withHeader = trimmed;
  } else if (/^\d/.test(trimmed[0] ?? "")) {
    // Første tegn er siffer → mangler header
    withHeader = TREND_SUMMARY_HEADER + "\n" + trimmed;
  } else {
    withHeader = trimmed;
  }

  // 2) Fyll inn date-kolonnen basert på profile_version
  const lines = withHeader.split("\n").filter((l) => l.length > 0);
  if (lines.length <= 1) return withHeader;

  const header = lines[0];
  const rows = lines.slice(1);

  const fixedRows = rows.map((line) => {
    const cols = line.split(",");

    // Vi forventer minst 10 kolonner i henhold til header
    if (cols.length < 10) return line;

    const dateCol = cols[1];
    const profileVersion = cols[7];

    // Hvis date mangler, prøv å hente YYYYMMDD fra profile_version
    if ((!dateCol || dateCol === "") && profileVersion) {
      const parts = profileVersion.split("-");
      const tail = parts[parts.length - 1]; // f.eks. "20251119"

      if (tail && tail.length === 8 && /^\d+$/.test(tail)) {
        const yyyy = tail.slice(0, 4);
        const mm = tail.slice(4, 6);
        const dd = tail.slice(6, 8);
        cols[1] = `${yyyy}-${mm}-${dd}`; // f.eks. 2025-11-19
      }
    }

    return cols.join(",");
  });

  console.log("[API] normalizeSummaryCsv ferdig", {
    firstRow: fixedRows[0],
  });

  return [header, ...fixedRows].join("\n");
}

export async function fetchCsv(path: string): Promise<string> {
  // Sørg for at path alltid starter med "/"
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = `${BACKEND_BASE}${normalizedPath}`;

  console.log("[API] fetchCsv →", url);

  const res = await fetch(url);

  if (!res.ok) {
    throw new Error(`Failed to fetch CSV: ${res.status} ${res.statusText}`);
  }

  const raw = await res.text();
  // Her sender vi *full URL* inn til normalizeSummaryCsv, så loggen matcher faktisk requesten
  return normalizeSummaryCsv(url, raw);
}

/**
 * Hent en session (legacy):
 * - id === "mock" eller BASE mangler → bruk mockSession (kilde: "mock")
 * - ellers → GET {BASE}/api/analyze_session?id={id} (kilde: "live")
 * Validerer alltid med Zod + semver.
 * Støtter timeout og ekstern AbortSignal.
 */
export async function fetchSession(
  id: string,
  options?: { timeoutMs?: number; signal?: AbortSignal }
): Promise<FetchSessionResult> {
  try {
    const base = normalizeBase(BASE);

    // MOCK eller manglende BASE → mock-kilde
    if (id === "mock" || !base) {
      await delay(150);

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

    // LIVE (legacy analyze_session)
    const url = buildAnalyzeUrl(base, id);
    const resp = await fetchWithTimeout(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      timeoutMs: options?.timeoutMs ?? 10_000,
      signal: options?.signal,
    });

    if (!resp.ok) {
      // Prøv å hente feilkropp (tekst) for mer nyttig tilbakemelding
      const text = await safeReadText(resp);
      return {
        ok: false,
        error: `HTTP ${resp.status} ${resp.statusText}${
          text ? ` – ${text}` : ""
        }`,
        source: "live",
      };
    }

    // Forsøk å parse JSON
    const json = await parseJsonSafe(resp);
    if (typeof json === "string") {
      // parseJsonSafe returnerer string når backend ikke sendte JSON
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
      return {
        ok: false,
        error: `Ugyldig respons fra backend: ${parsed.error}`,
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

    return { ok: true, data: parsed.data, source: "live" };
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : String(e);
    return {
      ok: false,
      error: message,
      source: BASE ? ("live" as const) : ("mock" as const),
    };
  }
}

/* ------------------------------------------------------------------
 * Sprint 15 – Nye API-funksjoner (analyze, profile, trend)
 * Basert på Layer 1 MASTER SPEC.
 * Alle bruker relative /api-URLer + fetchJSON (credentials: 'include').
 * ------------------------------------------------------------------ */

const API_ROOT = "/api";

// Enkel CSV-parser: tekst → string[][]
function parseCsv(text: string): CsvRows {
  if (!text.trim()) return [];
  return text
    .trim()
    .split("\n")
    .map((line) => line.split(","));
}

/**
 * analyze(sessionId)
 * POST /api/sessions/{id}/analyze
 * Returnerer AnalyzeResponse eller undefined ved AbortError.
 */
export async function analyze(
  sessionId: string,
  opts?: { signal?: AbortSignal }
): Promise<AnalyzeResponse | undefined> {
  const url = `${API_ROOT}/sessions/${encodeURIComponent(sessionId)}/analyze`;
  const res = await fetchJSON<AnalyzeResponse>(url, {
    method: "POST",
    signal: opts?.signal,
  });
  return res;
}

/**
 * getProfile()
 * GET /api/profile/get
 */
export async function getProfile(
  opts?: { signal?: AbortSignal }
): Promise<Profile | undefined> {
  const url = `${API_ROOT}/profile/get`;
  const res = await fetchJSON<Profile>(url, {
    method: "GET",
    signal: opts?.signal,
  });
  return res;
}

/**
 * setProfile(profile)
 * PUT /api/profile/save
 */
export async function setProfile(
  profile: Profile,
  opts?: { signal?: AbortSignal }
): Promise<Profile | undefined> {
  const url = `${API_ROOT}/profile/save`;
  const res = await fetchJSON<Profile>(url, {
    method: "PUT",
    signal: opts?.signal,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(profile),
  });
  return res;
}

/**
 * getTrendSummary()
 * GET /api/trend/summary.csv
 * Tom / timeout → rows: [].
 */
export async function getTrendSummary(
  opts?: { signal?: AbortSignal }
): Promise<TrendSummary> {
  const url = `${API_ROOT}/trend/summary.csv`;
  const raw = await fetchJSON<string | unknown>(url, {
    method: "GET",
    signal: opts?.signal,
  });

  if (typeof raw === "string") {
    return { rows: parseCsv(raw) };
  }

  // AbortError (undefined) eller tomt objekt → ingen rader
  return { rows: [] };
}

/**
 * getTrendPivot(metric, profileVersion)
 * GET /api/trend/pivot/<metric>.csv?profile_version=<pv>
 */
export async function getTrendPivot(
  metric: string,
  profileVersion: number,
  opts?: { signal?: AbortSignal }
): Promise<TrendPivot> {
  const qs = new URLSearchParams({
    profile_version: String(profileVersion),
  }).toString();
  const url = `${API_ROOT}/trend/pivot/${encodeURIComponent(
    metric
  )}.csv?${qs}`;

  const raw = await fetchJSON<string | unknown>(url, {
    method: "GET",
    signal: opts?.signal,
  });

  if (typeof raw === "string") {
    return { rows: parseCsv(raw) };
  }

  return { rows: [] };
}

/**
 * getSessionsList()
 * GET /api/sessions/list
 * Defensive: håndterer både ren liste og { value: [...] }-wrapper.
 */
export async function getSessionsList(
  opts?: { signal?: AbortSignal }
): Promise<SessionInfo[]> {
  const url = `${API_ROOT}/sessions/list`;

  const res = await fetchJSON<SessionInfo[] | { value?: unknown } | unknown>(
    url,
    {
      method: "GET",
      signal: opts?.signal,
    }
  );

  // Case 1: backend sender ren liste
  if (Array.isArray(res)) {
    return res as SessionInfo[];
  }

  // Case 2: backend wrapper i { value: [...] }
  if (
    res &&
    typeof res === "object" &&
    Array.isArray((res as { value?: unknown }).value)
  ) {
    const raw = (res as { value: unknown[] }).value;

    // Map til SessionInfo – tillat at session_id mangler inntil backend er helt på plass
    const mapped: SessionInfo[] = raw.map((item) => {
      const obj = item as Record<string, unknown>;

      const session_id =
        typeof obj.session_id === "string" ? obj.session_id : "";

      const ride_id =
        typeof obj.ride_id === "string" ? obj.ride_id : null;

      const label = typeof obj.label === "string" ? obj.label : null;

      const started_at =
        typeof obj.started_at === "string" ? obj.started_at : null;

      const mode =
        typeof obj.mode === "string" &&
        (obj.mode === "indoor" || obj.mode === "outdoor")
          ? (obj.mode as SessionInfo["mode"])
          : null;

      const weather_source =
        typeof obj.weather_source === "string" ? obj.weather_source : null;

      const profile_version =
        typeof obj.profile_version === "string"
          ? obj.profile_version
          : null;

      return {
        session_id,
        ride_id,
        label,
        started_at,
        mode,
        weather_source,
        profile_version,
      };
    });

    return mapped;
  }

  // Fallback: ingenting vi kjenner igjen
  return [];
}
