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
  const mode = (viteEnv.MODE ?? process.env?.NODE_ENV ?? "development").toLowerCase();
  const useMock = (viteEnv.VITE_USE_MOCK ?? "").toLowerCase() === "true";
  const backend = viteEnv.VITE_BACKEND_URL;

  if (useMock) return "";            // mock => same-origin (/api...)
  if (mode !== "production") return ""; // dev/test => same-origin (/api...)
  return backend ?? "";              // prod => bruk eksplisitt backend hvis satt
}

/**
 * Gjør absolutte API-URLer om til relative /api-URLer når vi er i dev eller mock.
 * Eksempel: http://localhost:8000/api/trends?x -> /api/trends?x
 */
function normalizeApiUrl(input: string): string {
  const viteEnv = readViteEnv();
  const mode = (viteEnv.MODE ?? process.env?.NODE_ENV ?? "development").toLowerCase();
  const useMock = (viteEnv.VITE_USE_MOCK ?? "").toLowerCase() === "true";

  // Kun i mock eller ikke-produksjon tvinger vi same-origin
  if (useMock || mode !== "production") {
    // Plukk ut /api-path fra absolutte URLer
    try {
      const url = new URL(input, typeof window !== "undefined" ? window.location.href : "http://localhost");
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
 * Henter JSON og kaster feil hvis svaret ikke er ok.
 */
export async function fetchJSON<T = unknown>(
  input: string,
  init?: RequestInit
): Promise<T> {
  const normalized = normalizeApiUrl(input);

  const res = await fetch(normalized, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${res.statusText} – ${text}`);
  }

  const data: T = (await res.json()) as T;
  return data;
}
