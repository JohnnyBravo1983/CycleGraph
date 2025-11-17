// frontend/src/lib/fetchJSON.ts

/**
 * Les Vite-miljø trygt
 */
function readViteEnv(): Record<string, string | undefined> {
  return (
    (typeof import.meta !== "undefined"
      ? (import.meta as unknown as { env?: Record<string, string | undefined> }).env
      : undefined) ?? {}
  );
}

/**
 * Returnerer backend-base basert på Vite-miljø og .env.local.
 * I dev/test og/eller mock skal vi bruke same-origin slik at Vite proxy/mocks tar over.
 */
export function getBackendBase(): string {
  const viteEnv = readViteEnv();
  const mode = (viteEnv.MODE ?? "development").toLowerCase();
  const useMock = (viteEnv.VITE_USE_MOCK ?? "").toLowerCase() === "true";
  const backend = viteEnv.VITE_BACKEND_URL;

  if (useMock) return ""; // mock => same-origin (/api...)
  if (mode !== "production") return ""; // dev/test => same-origin (/api...)
  return backend ?? ""; // prod => bruk eksplisitt backend hvis satt
}

/**
 * Gjør absolutte API-URLer om til relative /api-URLer når vi er i dev eller mock.
 * Eksempel: http://localhost:8000/api/trends?x -> /api/trends?x
 */
function normalizeApiUrl(input: string): string {
  const viteEnv = readViteEnv();
  const mode = (viteEnv.MODE ?? "development").toLowerCase();
  const useMock = (viteEnv.VITE_USE_MOCK ?? "").toLowerCase() === "true";

  // Kun i mock eller ikke-produksjon tvinger vi same-origin
  if (useMock || mode !== "production") {
    try {
      const url = new URL(
        input,
        typeof window !== "undefined" ? window.location.href : "http://localhost"
      );
      if (url.pathname.startsWith("/api")) {
        return `${url.pathname}${url.search}${url.hash}`;
      }
    } catch {
      // input er ikke en absolutt URL – fint, bare la den gå videre
    }
  }
  return input;
}

/**
 * Les en boolsk feature toggle fra Vite-miljøet.
 * Godtar: "true"/"1"/"yes" (case-insensitive) som sann.
 */
function readEnvFlag(name: string): boolean {
  const viteEnv = readViteEnv();
  const raw = viteEnv[name];
  if (!raw) return false;
  const v = raw.toLowerCase().trim();
  return v === "true" || v === "1" || v === "yes";
}

/** Global toggle for å bruke live-endepunkt for trends */
export const USE_LIVE_TRENDS = readEnvFlag("VITE_USE_LIVE_TRENDS");

/** Sjekk om en feil er en AbortError fra fetch */
function isAbortError(err: unknown): boolean {
  return !!(err && typeof err === "object" && (err as { name?: string }).name === "AbortError");
}

/**
 * Sentralt fetch-helper for JSON eller tekst (CSV/annet).
 *
 * - Bruker normalizeApiUrl for dev/mock same-origin.
 * - Alltid credentials: 'include' (backend-kontrakt i Sprint 15).
 * - 10s timeout via AbortController.
 * - Returnerer:
 *    - `T` (parsed JSON eller tekst) ved suksess
 *    - `undefined` ved AbortError (timeout eller ekstern abort)
 * - Kaster på andre feil og non-2xx statuskoder.
 */
export async function fetchJSON<T = unknown>(
  input: string,
  init: RequestInit & { signal?: AbortSignal } = {}
): Promise<T | undefined> {
  const normalized = normalizeApiUrl(input);

  const controller = new AbortController();
  const timeoutMs = 10000;
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const { signal, ...restInit } = init;

  // Hvis caller gir egen signal, koble den til vår controller
  if (signal) {
    if (signal.aborted) {
      clearTimeout(timeoutId);
      return undefined;
    }
    signal.addEventListener(
      "abort",
      () => {
        controller.abort();
      },
      { once: true }
    );
  }

  try {
    const res = await fetch(normalized, {
      ...restInit,
      credentials: "include",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(restInit.headers ?? {}),
      },
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status} ${res.statusText} – ${text}`);
    }

    const contentType = res.headers.get("content-type") || "";

    // JSON → parse & return
    if (contentType.includes("application/json")) {
      return (await res.json()) as T;
    }

    // Ellers returnerer vi tekst (CSV/raw) som T
    const text = await res.text();
    return text as unknown as T;
  } catch (err) {
    clearTimeout(timeoutId);

    if (isAbortError(err)) {
      // Stille fallback ved avbrutt fetch (inkl. timeout)
      return undefined;
    }
    throw err;
  }
}

/** Eksplisitt valg av kilde pr kall */
export type TrendsMode = "live" | "mock";

/**
 * Bygg URL for trends-endepunkt avhengig av valgt modus.
 * - mode === "live" → /api/trends?sessionId=...
 * - mode === "mock" → mock-fil
 * - hvis mode er udefinert → styres av USE_LIVE_TRENDS
 */
function buildTrendsUrl(sessionId: string, mode?: TrendsMode): string {
  const effective: TrendsMode = mode ?? (USE_LIVE_TRENDS ? "live" : "mock");

  if (effective === "live") {
    const base = getBackendBase(); // tom streng i dev/mock → same-origin
    const qs = new URLSearchParams({ sessionId }).toString();
    const url = `${base ? `${base.replace(/\/$/, "")}` : ""}/api/trends?${qs}`;
    return normalizeApiUrl(url);
  }

  // mock
  return `/mock/trends_${encodeURIComponent(sessionId)}.json`;
}

/**
 * Hent trends-data. Brukes av TrendsChart/AnalysisPanel.
 * - `mode` kan overstyre USE_LIVE_TRENDS pr kall.
 * - Returnerer `undefined` ved abort.
 */
export async function fetchTrends<T = unknown>(
  sessionId: string,
  opts?: { signal?: AbortSignal; mode?: TrendsMode }
): Promise<T | undefined> {
  const url = buildTrendsUrl(sessionId, opts?.mode);
  return fetchJSON<T>(url, { signal: opts?.signal });
}
