// frontend/src/lib/fetchJSON.ts

const PROD_FALLBACK_API = "https://api.cyclegraph.app";

/**
 * Les Vite-miljø trygt (funker også i build/SSR-kontekst)
 */
function readViteEnv(): Record<string, string | undefined> {
  return (
    (typeof import.meta !== "undefined"
      ? (import.meta as unknown as { env?: Record<string, string | undefined> }).env
      : undefined) ?? {}
  );
}

/**
 * Returnerer backend-base basert på miljø.
 *
 * - dev/test/mock  → same-origin (/api/...)
 * - prod:
 *    - hvis VITE_BACKEND_URL finnes → bruk den
 *    - ellers → fallback til https://api.cyclegraph.app
 *
 * Dette beskytter oss mot:
 * - feil Vercel rewrites
 * - HTML SPA fallback på /api/*
 */
export function getBackendBase(): string {
  const viteEnv = readViteEnv();

  const mode =
    (viteEnv.MODE ?? process.env?.NODE_ENV ?? "development").toLowerCase();

  const useMock = (viteEnv.VITE_USE_MOCK ?? "").toLowerCase() === "true";
  const backend = (viteEnv.VITE_BACKEND_URL ?? "").trim();

  // mock => same-origin
  if (useMock) return "";

  // dev/test => same-origin (Vite proxy eller relative kall)
  if (mode !== "production") return "";

  // prod: eksplisitt backend hvis satt
  if (backend) return backend;

  // prod fallback (kritisk for å unngå HTML fra Vercel)
  return PROD_FALLBACK_API;
}

/**
 * Minimal fetch-helper for JSON API
 * - inkluderer cookies (auth)
 * - beskytter mot HTML-respons (Vercel SPA)
 */
export async function fetchJSON<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const base = getBackendBase();

  const url =
    path.startsWith("http")
      ? path
      : `${base}${path.startsWith("/") ? "" : "/"}${path}`;

  const res = await fetch(url, {
    ...init,
    credentials: "include", // 🔑 auth cookies
    headers: {
      Accept: "application/json",
      ...(init.headers ?? {}),
    },
  });

  const ct = (res.headers.get("content-type") ?? "").toLowerCase();

  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(
      `HTTP ${res.status} ${res.statusText} url=${url} ct=${ct} body=${txt.slice(
        0,
        400
      )}`
    );
  }

  // ⚠️ Viktig: hvis vi får HTML her, er det nesten alltid Vercel rewrite-feil
  if (ct.includes("text/html")) {
    const txt = await res.text().catch(() => "");
    throw new Error(
      `Expected JSON but got HTML (likely Vercel SPA fallback)
url=${url}
body=${txt.slice(0, 200)}`
    );
  }

  return (await res.json()) as T;
}
