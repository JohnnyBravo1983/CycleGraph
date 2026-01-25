// frontend/src/lib/fetchJSON.ts

const PROD_FALLBACK_API = "https://api.cyclegraph.app";

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
  const backend = (viteEnv.VITE_BACKEND_URL ?? "").trim();

  if (useMock) return "";               // mock => same-origin (/api...)
  if (mode !== "production") return ""; // dev/test => same-origin (/api...)

  // ✅ PROD: hvis env mangler / rewrites ikke fungerer, fall tilbake til api.cyclegraph.app
  if (backend) return backend;
  return PROD_FALLBACK_API;
}

/**
 * Minimal fetch helper med cookies inkludert (auth cookies)
 */
export async function fetchJSON<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const base = getBackendBase();
  const url = path.startsWith("http")
    ? path
    : `${base}${path.startsWith("/") ? "" : "/"}${path}`;

  const res = await fetch(url, {
    ...init,
    // ✅ VIKTIG: cookies må følge med til api.cyclegraph.app
    credentials: "include",
    headers: {
      "Accept": "application/json",
      ...(init.headers ?? {}),
    },
  });

  const ct = (res.headers.get("content-type") ?? "").toLowerCase();

  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(
      `HTTP ${res.status} ${res.statusText} url=${url} ct=${ct} body=${txt.slice(0, 400)}`
    );
  }

  // Hvis noe fortsatt svarer HTML, gi en tydelig feilmelding (debug)
  if (ct.includes("text/html")) {
    const txt = await res.text().catch(() => "");
    throw new Error(`Expected JSON but got HTML url=${url} body=${txt.slice(0, 200)}`);
  }

  return (await res.json()) as T;
}
