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

/** Bygg URL til analyze_session */
function buildAnalyzeUrl(base: string, id: string): string {
  return `${base}/api/analyze_session?id=${encodeURIComponent(id)}`;
}

/**
 * Hent en session:
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

    // LIVE
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
