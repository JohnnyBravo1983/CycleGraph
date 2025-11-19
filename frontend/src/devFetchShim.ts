// frontend/src/devFetchShim.ts
// Intercept dev/mock-requests og tving same-origin (/api/...) i stedet for absolutte :8000-URLer.
// I tillegg: normaliser /api/trend/summary.csv slik at frontend alltid får header + dato.

import { normalizeSummaryCsv } from "./lib/api";

type ViteEnv = Record<string, string | undefined>;

function readViteEnv(): ViteEnv {
  return (
    (typeof import.meta !== "undefined"
      ? (import.meta as unknown as { env?: ViteEnv }).env
      : undefined) ?? {}
  );
}

const viteEnv = readViteEnv();
const mode = (viteEnv.MODE ?? "development").toLowerCase();
const useMock = (viteEnv.VITE_USE_MOCK ?? "").toLowerCase() === "true";

// Bare i dev/test eller mock
if (typeof window !== "undefined" && (useMock || mode !== "production")) {
  const origFetch = window.fetch.bind(window);

  function toUrlString(input: string | Request | URL): string {
    if (typeof input === "string") return input;
    if (input instanceof Request) return input.url;
    // URL -> string for å matche fetch-signaturen i eldre TS/lib.dom
    return input.toString();
  }

  window.fetch = (...args: Parameters<typeof fetch>): ReturnType<typeof fetch> => {
    const [input, init] = args;
    const urlStr = toUrlString(input as string | Request | URL);

    let finalInput: string | Request = input as string | Request;

    // 1) Eventuell rewrite av http://localhost:8000/api/... → /api/...
    try {
      const url = new URL(urlStr, window.location.href);
      if (url.host === "localhost:8000" && url.pathname.startsWith("/api")) {
        const rewritten = `${url.pathname}${url.search}${url.hash}`;
        finalInput = rewritten;
      }
    } catch {
      // Ikke en absolutt URL, la den gå videre
    }

    // Sørg for at vi alltid sender string/Request videre (ikke URL-objekt)
    if (!(typeof finalInput === "string" || finalInput instanceof Request)) {
      finalInput = urlStr;
    }

    // 2) Kall original fetch, og wrap responsen for summary.csv
    return origFetch(finalInput, init).then(async (res) => {
      try {
        const targetUrl =
          res.url ||
          (typeof finalInput === "string" ? finalInput : finalInput.url);

        if (targetUrl.includes("summary.csv")) {
          const raw = await res.text();
          const normalized = normalizeSummaryCsv(targetUrl, raw);

          console.log(
            "[devFetchShim] normalized summary.csv, first80=",
            normalized.slice(0, 80),
          );

          // Returner en ny Response med normalisert body,
          // men behold status + headers fra originalen
          return new Response(normalized, {
            status: res.status,
            statusText: res.statusText,
            headers: res.headers,
          });
        }
      } catch (e) {
        console.warn("[devFetchShim] failed to normalize summary.csv", e);
      }

      // Alle andre kall → uendret respons
      return res;
    });
  };
}
