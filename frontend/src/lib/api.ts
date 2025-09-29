// frontend/src/lib/api.ts
import type { SessionReport } from "../types/session";
import { mockSession } from "./mockSession";
import { safeParseSession, ensureSemver } from "./schema";

type Ok = { ok: true; data: SessionReport; source: "mock" | "live" };
type Err = { ok: false; error: string; source?: "mock" | "live" };
export type FetchSessionResult = Ok | Err;

// Hent Vite-variabler (.env.local)
const BASE = import.meta.env.VITE_BACKEND_URL as string | undefined;

// Hjelper: fjern trailing slash
function normalizeBase(url?: string): string | undefined {
  if (!url) return undefined;
  return url.replace(/\/+$/, "");
}

// Litt ventetid for realisme i mock
const delay = (ms: number) => new Promise((res) => setTimeout(res, ms));

/** Dev-bryter: legg til ?simulateInvalid=1 i URL for å teste ugyldig/manglende schema_version */
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

/**
 * Hent en session:
 * - id === "mock" eller BASE mangler → bruk mockSession
 * - ellers → GET {BASE}/api/analyze_session?id={id}
 * Validerer alltid med Zod + semver.
 */
export async function fetchSession(id: string): Promise<FetchSessionResult> {
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
    const url = `${base}/api/analyze_session?id=${encodeURIComponent(id)}`;
    const resp = await fetch(url, { headers: { Accept: "application/json" } });

    if (!resp.ok) {
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
    let json: unknown;
    try {
      json = await resp.json();
    } catch {
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
    return { ok: false, error: message, source: BASE ? ("live" as const) : ("mock" as const) };
  }
}

async function safeReadText(res: Response): Promise<string> {
  try {
    return await res.text();
  } catch {
    return "";
  }
}
